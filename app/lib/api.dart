import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'models.dart';

/// 401：token 失效（服务端明确拒绝）
class Api401 implements Exception {
  @override
  String toString() => '登录已过期，请重新登录';
}

/// 网络层失败（无连接/超时/DNS/TLS）——这类错误才允许回退缓存
class ApiNet implements Exception {
  final String msg;
  ApiNet(this.msg);
  @override
  String toString() => '网络错误：$msg';
}

/// HTTP 层失败（服务器返回了非 2xx/401 状态）——不回退缓存，避免陈旧数据冒充真实响应
class ApiHttp implements Exception {
  final int code;
  final String msg;
  ApiHttp(this.code, [this.msg = '']);
  @override
  String toString() => '服务器错误 $code${msg.isNotEmpty ? '：$msg' : ''}';
}

/// 面向用户的错误文案
String errText(Object e) {
  if (e is Api401) return '登录已过期，请重新登录';
  if (e is ApiNet) return '网络连接失败，请检查网络后重试';
  if (e is ApiHttp) return e.msg.isNotEmpty ? e.msg : '服务器错误（${e.code}）';
  return e.toString();
}

/// GET query 构造：null/空串/false 不传，true 传 1，列表逗号分隔
String buildQuery(Map<String, Object?>? q) {
  if (q == null) return '';
  final List<String> parts = <String>[];
  q.forEach((String k, Object? v) {
    if (v == null || v == '' || v == false) return;
    final String s;
    if (v == true) {
      s = '1';
    } else if (v is List) {
      if (v.isEmpty) return;
      s = v.join(',');
    } else {
      s = v.toString();
    }
    parts.add('${Uri.encodeQueryComponent(k)}=${Uri.encodeQueryComponent(s)}');
  });
  return parts.isEmpty ? '' : '?${parts.join('&')}';
}

class Api {
  static String base = 'https://luck.021209.xyz';
  static String token = '';
  static const int appBuild = 1; // CI 构建时替换为 run_number
  static const String _kBase = 'kb_base';
  static const String _kToken = 'kb_token';
  static const String _kFont = 'kb_font';
  static const String _kAdmin = 'kb_admin';
  static double fontSize = 15;
  static bool admin = false;

  /// 全局 401 回调：main.dart 注入，负责跳回登录页并提示「登录已过期」
  static void Function()? onUnauthorized;

  /// 登录页待展示的会话提示（401 后写入，登录页消费一次）
  static String? pendingAuthMsg;

  /// 最近一次 get() 是否来自离线缓存
  static bool lastFromCache = false;
  static DateTime? lastCacheTime;

  static const int _cacheCap = 300;

  static Future<void> load() async {
    final SharedPreferences p = await SharedPreferences.getInstance();
    base = p.getString(_kBase) ?? base;
    token = p.getString(_kToken) ?? '';
    fontSize = p.getDouble(_kFont) ?? 15;
    admin = p.getBool(_kAdmin) ?? false;
    await _migrateOnce(p);
  }

  /// 一次性迁移：清掉 v1 时代的缓存与位置键
  static Future<void> _migrateOnce(SharedPreferences p) async {
    if (p.getBool('mig_v3') == true) return;
    for (final String k in p.getKeys().toList()) {
      if (k.startsWith('cache:') ||
          k.startsWith('cache2:') ||
          k.startsWith('qpos:')) {
        await p.remove(k);
      }
    }
    await p.setBool('mig_v3', true);
  }

  static Future<void> save(
      {String? base, String? token, double? fontSize, bool? admin}) async {
    final SharedPreferences p = await SharedPreferences.getInstance();
    if (base != null) {
      Api.base = base;
      await p.setString(_kBase, base);
    }
    if (token != null) {
      Api.token = token;
      await p.setString(_kToken, token);
    }
    if (fontSize != null) {
      Api.fontSize = fontSize;
      await p.setDouble(_kFont, fontSize);
    }
    if (admin != null) {
      Api.admin = admin;
      await p.setBool(_kAdmin, admin);
    }
  }

  /// 注销/会话过期：清 token + 当前账号缓存（其他账号缓存保留，防串号）
  static Future<void> clearSession() async {
    await _clearAcctCache();
    await save(token: '', admin: false);
  }

  /// 地址校验：必须 http(s)，不允许 userinfo/查询串/片段；公网地址强制 https
  static String? validateBase(String v) {
    final Uri? u = Uri.tryParse(v);
    if (u == null || !u.hasScheme || u.host.isEmpty) return '地址格式无效';
    if (u.scheme != 'https' && u.scheme != 'http') return '仅支持 http(s)';
    if (u.userInfo.isNotEmpty || u.hasQuery || u.hasFragment) {
      return '地址不应包含账号信息/参数';
    }
    if (u.scheme == 'http' && !_isPrivateHost(u.host)) {
      return '公网地址必须使用 https';
    }
    return null;
  }

  static bool _isPrivateHost(String h) {
    if (h == 'localhost' || h == '127.0.0.1' || h == '::1') return true;
    if (h.startsWith('10.') || h.startsWith('192.168.')) return true;
    final RegExpMatch? m = RegExp(r'^172\.(\d{1,2})\.').firstMatch(h);
    if (m != null) {
      final int n = int.tryParse(m.group(1) ?? '') ?? 0;
      if (n >= 16 && n <= 31) return true;
    }
    return false;
  }

  // ==================== 缓存（按账号命名空间隔离） ====================

  static String get _acct => token.isEmpty ? 'anon' : _fnv(token);
  static String get _cachePfx => 'cache3:$_acct:';

  /// FNV-1a：仅作键命名用，非加密用途
  static String _fnv(String s) {
    int h = 0x811c9dc5;
    for (final int c in utf8.encode(s)) {
      h ^= c;
      h = (h * 0x01000193) & 0xffffffff;
    }
    return h.toRadixString(16).padLeft(8, '0');
  }

  /// 位置/进度等持久键的派生（避免超长原始串作 key）
  static String prefKey(String prefix, String raw) => '$prefix:${_fnv(raw)}';

  static Future<void> _cacheWrite(String key, String body) async {
    final SharedPreferences p = await SharedPreferences.getInstance();
    await p.setString(
        key,
        jsonEncode(<String, dynamic>{
          't': DateTime.now().millisecondsSinceEpoch,
          'b': body,
        }));
    final List<String> keys =
        p.getKeys().where((String k) => k.startsWith(_cachePfx)).toList();
    if (keys.length > _cacheCap) {
      final Map<String, int> aged = <String, int>{};
      for (final String k in keys) {
        try {
          final dynamic j = jsonDecode(p.getString(k) ?? '');
          aged[k] = j is Map && j['t'] is num ? (j['t'] as num).toInt() : 0;
        } catch (_) {
          aged[k] = 0;
        }
      }
      keys.sort((String a, String b) => (aged[a] ?? 0).compareTo(aged[b] ?? 0));
      for (final String k in keys.take(keys.length - _cacheCap)) {
        await p.remove(k);
      }
    }
  }

  static Future<dynamic> _cacheRead(String key) async {
    final SharedPreferences p = await SharedPreferences.getInstance();
    final String? c = p.getString(key);
    if (c == null) return null;
    try {
      final dynamic j = jsonDecode(c);
      if (j is! Map) return null;
      final int t = j['t'] is num ? (j['t'] as num).toInt() : 0;
      final dynamic data = jsonDecode(j['b'] as String);
      lastCacheTime = DateTime.fromMillisecondsSinceEpoch(t);
      return data;
    } catch (_) {
      return null;
    }
  }

  /// 当前账号缓存大小（字节近似）
  static Future<int> cacheBytes() async {
    final SharedPreferences p = await SharedPreferences.getInstance();
    int n = 0;
    for (final String k in p.getKeys()) {
      if (k.startsWith(_cachePfx)) n += (p.getString(k) ?? '').length;
    }
    return n;
  }

  static Future<void> _clearAcctCache() async {
    final SharedPreferences p = await SharedPreferences.getInstance();
    for (final String k in p.getKeys().toList()) {
      if (k.startsWith(_cachePfx)) await p.remove(k);
    }
  }

  static Future<void> cacheClear() => _clearAcctCache();

  // ==================== 请求 ====================

  static Never _netRethrow(Object e) {
    if (e is Api401 || e is ApiHttp || e is ApiNet) throw e;
    throw ApiNet(e.toString());
  }

  static Future<void> _expire() async {
    await clearSession();
    onUnauthorized?.call();
  }

  static String _errMsg(http.Response r) {
    try {
      final dynamic j = jsonDecode(utf8.decode(r.bodyBytes));
      if (j is Map) {
        final dynamic m = j['detail'] ?? j['message'] ?? j['err'];
        if (m is String) return m;
        if (m != null) return jsonEncode(m);
      }
    } catch (_) {}
    return '';
  }

  static dynamic _decode(http.Response r) {
    if (r.bodyBytes.isEmpty) return null;
    return jsonDecode(utf8.decode(r.bodyBytes));
  }

  /// path 不含 /api 前缀，如 '/quiz/questions'
  static Future<http.Response> _send(String method, String path,
      {Map<String, Object?>? query,
      Object? body,
      int secs = 60,
      bool authPath = false}) async {
    final Uri uri = Uri.parse('$base/api$path${buildQuery(query)}');
    http.Response r;
    try {
      final http.Request req = http.Request(method, uri);
      if (token.isNotEmpty) req.headers['X-Token'] = token;
      if (body != null) {
        req.headers['Content-Type'] = 'application/json';
        req.body = jsonEncode(body);
      }
      final http.StreamedResponse s =
          await req.send().timeout(Duration(seconds: secs));
      r = await http.Response.fromStream(s);
    } catch (e) {
      _netRethrow(e);
    }
    if (r.statusCode == 401 && !authPath) {
      await _expire();
      throw Api401();
    }
    if (r.statusCode < 200 || r.statusCode >= 300) {
      throw ApiHttp(r.statusCode, _errMsg(r));
    }
    return r;
  }

  /// GET：网络类失败且 cache=true 时回退离线缓存（lastFromCache=true）
  static Future<dynamic> get(String path,
      {Map<String, Object?>? query, bool cache = true}) async {
    lastFromCache = false;
    final String key = '$_cachePfx$path${buildQuery(query)}';
    try {
      final http.Response r = await _send('GET', path, query: query);
      if (cache) unawaited(_cacheWrite(key, utf8.decode(r.bodyBytes)));
      return _decode(r);
    } on ApiNet {
      if (cache) {
        final dynamic c = await _cacheRead(key);
        if (c != null) {
          lastFromCache = true;
          return c;
        }
      }
      rethrow;
    }
  }

  static Future<dynamic> post(String path, [Object? body, int secs = 60]) async {
    return _decode(await _send('POST', path, body: body, secs: secs));
  }

  static Future<dynamic> put(String path, [Object? body]) async {
    return _decode(await _send('PUT', path, body: body));
  }

  static Future<dynamic> del(String path, {Map<String, Object?>? query}) async {
    return _decode(await _send('DELETE', path, query: query));
  }

  /// 管理员上传图片，成功返回服务端给出的相对路径（如 /uimg/xxx.webp），失败返回 null
  static Future<String?> uploadImage(String filePath) async {
    try {
      final http.MultipartRequest req =
          http.MultipartRequest('POST', Uri.parse('$base/api/admin/images'));
      req.headers['X-Token'] = token;
      req.files.add(await http.MultipartFile.fromPath('file', filePath));
      final http.StreamedResponse s =
          await req.send().timeout(const Duration(seconds: 120));
      final http.Response r = await http.Response.fromStream(s);
      if (r.statusCode == 401) {
        await _expire();
        throw Api401();
      }
      if (r.statusCode < 200 || r.statusCode >= 300) return null;
      final dynamic j = _decode(r);
      return j is Map && j['url'] is String ? j['url'] as String : null;
    } on Api401 {
      rethrow;
    } catch (_) {
      return null;
    }
  }

  // ==================== 账号 ====================

  static Future<AuthResult> _auth(String path, Map<String, Object?> body) async {
    final http.Response r =
        await _send('POST', path, body: body, secs: 30, authPath: true);
    final AuthResult a = AuthResult.fromJson(asMap(_decode(r)));
    if (a.token.isEmpty) throw ApiHttp(500, '服务器未返回登录凭证');
    await save(token: a.token, admin: a.user.isAdmin);
    return a;
  }

  /// 成功时已保存 token/admin；失败抛 ApiHttp/ApiNet（含服务端提示文案）
  static Future<AuthResult> login(String username, String password) =>
      _auth('/auth/login', <String, Object?>{
        'username': username,
        'password': password,
      });

  static Future<AuthResult> register(
          String username, String password, String inviteCode) =>
      _auth('/auth/register', <String, Object?>{
        'username': username,
        'password': password,
        'invite_code': inviteCode,
      });

  /// 通知服务端注销（失败忽略），并清本地会话
  static Future<void> logout() async {
    try {
      await _send('POST', '/auth/logout', secs: 10, authPath: true);
    } catch (_) {}
    await clearSession();
  }

  /// 检查新版本；有新 build 返回 VersionInfo，否则 null
  static Future<VersionInfo?> checkUpdate() async {
    try {
      final dynamic j = await get('/version', cache: false);
      final VersionInfo v = VersionInfo.fromJson(asMap(j));
      return v.build > appBuild ? v : null;
    } catch (_) {
      return null;
    }
  }
}
