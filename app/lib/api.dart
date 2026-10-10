import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// 401：token 失效（服务端明确拒绝）
class Api401 implements Exception {}

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

class Api {
  static String base = 'https://luck.021209.xyz';
  static String token = '';
  static const int appBuild = 1;  // CI 构建时替换为 run_number
  static const _kBase = 'kb_base';
  static const _kToken = 'kb_token';
  static double fontSize = 15;
  static const _kFont = 'kb_font';
  static bool admin = false;
  static const _kAdmin = 'kb_admin';

  /// 全局 401 回调：main.dart 注入，负责跳回登录页并提示「登录已过期」
  static void Function()? onUnauthorized;

  /// 登录页待展示的会话提示（401 后写入，登录页消费一次）
  static String? pendingAuthMsg;

  /// 最近一次 get() 是否来自离线缓存（页面可据此显示「离线数据」角标）
  static bool lastFromCache = false;
  static DateTime? lastCacheTime;

  /// 缓存条目上限（按账号隔离计数）
  static const _cacheCap = 300;

  static Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    base = p.getString(_kBase) ?? base;
    token = p.getString(_kToken) ?? '';
    fontSize = p.getDouble(_kFont) ?? 15;
    admin = p.getBool(_kAdmin) ?? false;
    await _migrateOnce(p);
  }

  /// 一次性迁移：清掉旧版无命名空间缓存与超长 qpos 键
  static Future<void> _migrateOnce(SharedPreferences p) async {
    if (p.getBool('mig_v2') == true) return;
    for (final k in p.getKeys().toList()) {
      if (k.startsWith('cache:') || k.startsWith('qpos:')) {
        await p.remove(k);
      }
    }
    await p.setBool('mig_v2', true);
  }

  static Future<void> save({String? base, String? token, double? fontSize, bool? admin}) async {
    final p = await SharedPreferences.getInstance();
    if (base != null) { Api.base = base; await p.setString(_kBase, base); }
    if (token != null) { Api.token = token; await p.setString(_kToken, token); }
    if (fontSize != null) { Api.fontSize = fontSize; await p.setDouble(_kFont, fontSize); }
    if (admin != null) { Api.admin = admin; await p.setBool(_kAdmin, admin); }
  }

  /// 注销/会话过期：清 token + 当前账号缓存（其他账号缓存保留，防串号）
  static Future<void> clearSession() async {
    await _clearAcctCache();
    await save(token: '', admin: false);
  }

  /// 服务端/自定义地址校验：必须 http(s)，不允许 userinfo/查询串/片段；
  /// 公网地址强制 https，http 仅放行私有网段（本地调试）
  static String? validateBase(String v) {
    final u = Uri.tryParse(v);
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
    final m = RegExp(r'^172\.(\d{1,2})\.').firstMatch(h);
    if (m != null) { final n = int.tryParse(m.group(1)!) ?? 0; if (n >= 16 && n <= 31) return true; }
    return false;
  }

  /// 拉取当前账号信息（含 admin 标记）
  static Future<void> refreshMe() async {
    try {
      final j = await get('/api/me', cache: false);
      await save(admin: j['admin'] == true);
    } catch (_) {}
  }

  /// 上传图片（管理员），成功返回 /uimg/ 相对路径
  static Future<String?> uploadImage(String filePath) async {
    try {
      final req = http.MultipartRequest('POST', Uri.parse('$base/api/admin/qimg'));
      req.headers['X-Token'] = token;
      req.files.add(await http.MultipartFile.fromPath('file', filePath));
      final r = await req.send().timeout(const Duration(seconds: 120));
      if (r.statusCode == 401) { await _expire(); throw Api401(); }
      final j = jsonDecode(utf8.decode(await r.stream.toBytes()));
      return j['ok'] == true ? j['url'] as String : null;
    } on Api401 {
      rethrow;
    } catch (_) {
      return null;
    }
  }

  // ==================== 缓存（按账号命名空间隔离） ====================

  /// token 派生的账号命名空间：不同账号缓存互不可见
  static String get _acct => token.isEmpty ? 'anon' : _fnv(token);
  static String get _cachePfx => 'cache2:$_acct:';

  /// FNV-1a：仅作键命名/去重用，非加密用途
  static String _fnv(String s) {
    var h = 0x811c9dc5;
    for (final c in utf8.encode(s)) {
      h ^= c;
      h = (h * 0x01000193) & 0xffffffff;
    }
    return h.toRadixString(16).padLeft(8, '0');
  }

  /// 公开：位置/进度等持久键也做同样派生，避免超长原始串作 key
  static String prefKey(String prefix, String raw) => '$prefix:${_fnv(raw)}';

  static Future<void> _cacheWrite(String key, String body) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(key, jsonEncode({'t': DateTime.now().millisecondsSinceEpoch, 'b': body}));
    // 超限则按写入时间淘汰最旧条目
    final keys = p.getKeys().where((k) => k.startsWith(_cachePfx)).toList();
    if (keys.length > _cacheCap) {
      final aged = <String, int>{};
      for (final k in keys) {
        try {
          aged[k] = (jsonDecode(p.getString(k) ?? '')['t'] ?? 0) as int;
        } catch (_) { aged[k] = 0; }
      }
      keys.sort((a, b) => (aged[a] ?? 0).compareTo(aged[b] ?? 0));
      for (final k in keys.take(keys.length - _cacheCap)) {
        await p.remove(k);
      }
    }
  }

  static Future<dynamic> _cacheRead(String key) async {
    final p = await SharedPreferences.getInstance();
    final c = p.getString(key);
    if (c == null) return null;
    try {
      final j = jsonDecode(c);
      lastCacheTime = DateTime.fromMillisecondsSinceEpoch((j['t'] ?? 0) as int);
      return jsonDecode(j['b'] as String);
    } catch (_) {
      return null;
    }
  }

  /// 缓存大小（当前账号，字节）
  static Future<int> cacheBytes() async {
    final p = await SharedPreferences.getInstance();
    var n = 0;
    for (final k in p.getKeys()) {
      if (k.startsWith(_cachePfx)) n += (p.getString(k) ?? '').length;
    }
    return n;
  }

  /// 清当前账号缓存
  static Future<void> _clearAcctCache() async {
    final p = await SharedPreferences.getInstance();
    for (final k in p.getKeys().toList()) {
      if (k.startsWith(_cachePfx)) await p.remove(k);
    }
  }

  static Future<void> cacheClear() => _clearAcctCache();

  // ==================== 请求 ====================

  /// 把 socket/timeout 等底层异常归一为 ApiNet
  static Never _netRethrow(Object e) {
    if (e is Api401 || e is ApiHttp || e is ApiNet) throw e;
    if (e is SocketException || e is TimeoutException ||
        e is http.ClientException || e is HandshakeException ||
        e is HttpException) {
      throw ApiNet(e.toString());
    }
    // 其他未知异常按网络类处理（如 TLS 细节异常），允许缓存兜底
    throw ApiNet(e.toString());
  }

  static Future<void> _expire() async {
    await clearSession();
    onUnauthorized?.call();
  }

  static Future<dynamic> get(String path, {bool cache = true}) async {
    lastFromCache = false;
    final key = '$_cachePfx$path';
    try {
      final r = await http.get(Uri.parse(base + path),
          headers: {'X-Token': token}).timeout(const Duration(seconds: 60));
      if (r.statusCode == 401) { await _expire(); throw Api401(); }
      if (r.statusCode == 200) {
        final body = utf8.decode(r.bodyBytes);
        if (cache && path.startsWith('/api/')) {
          unawaited(_cacheWrite(key, body));
        }
        return jsonDecode(body);
      }
      throw ApiHttp(r.statusCode);
    } on Api401 {
      rethrow;
    } on ApiHttp {
      rethrow;   // HTTP 错误不吃缓存——陈旧数据不能冒充真实响应
    } catch (e) {
      // 网络层失败才允许离线兜底
      try { _netRethrow(e); } on ApiNet {
        if (cache) {
          final c = await _cacheRead(key);
          if (c != null) { lastFromCache = true; return c; }
        }
        rethrow;
      }
    }
  }

  static Future<dynamic> post(String path, Map body, {int secs = 60}) async {
    http.Response r;
    try {
      r = await http.post(Uri.parse(base + path),
          headers: {'X-Token': token, 'Content-Type': 'application/json'},
          body: jsonEncode(body)).timeout(Duration(seconds: secs));
    } catch (e) {
      _netRethrow(e);
    }
    if (r.statusCode == 401) { await _expire(); throw Api401(); }
    if (r.statusCode >= 400) {
      String msg = '';
      try { msg = (jsonDecode(utf8.decode(r.bodyBytes))['err'] ?? '').toString(); } catch (_) {}
      throw ApiHttp(r.statusCode, msg);
    }
    return jsonDecode(utf8.decode(r.bodyBytes));
  }

  static Future<dynamic> del(String path, Map body) async {
    http.StreamedResponse r;
    try {
      final req = http.Request('DELETE', Uri.parse(base + path));
      req.headers.addAll({'X-Token': token, 'Content-Type': 'application/json'});
      req.body = jsonEncode(body);
      r = await req.send().timeout(const Duration(seconds: 60));
    } catch (e) {
      _netRethrow(e);
    }
    if (r.statusCode == 401) { await _expire(); throw Api401(); }
    if (r.statusCode >= 400) throw ApiHttp(r.statusCode);
    return jsonDecode(utf8.decode(await r.stream.toBytes()));
  }

  static Future<String?> login(String user, String pw) async {
    final j = await _postAuth('/api/login', {'user': user, 'pw': pw});
    return j;
  }

  static Future<String?> register(String user, String pw, String code) async {
    return await _postAuth('/api/register', {'user': user, 'pw': pw, 'code': code});
  }

  /// 返回 null=成功（已存 token），否则为错误消息
  static Future<String?> _postAuth(String path, Map body) async {
    try {
      final r = await http.post(Uri.parse('$base$path'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body)).timeout(const Duration(seconds: 30));
      final j = jsonDecode(utf8.decode(r.bodyBytes));
      if (j['ok'] == true) { await save(token: j['token'], admin: j['admin'] == true); return null; }
      return j['msg']?.toString() ?? '失败';
    } catch (e) {
      return '连接失败：$e';
    }
  }

  /// 检查新版本；有新 build 返回 {build,note}，否则 null
  static Future<Map<String, dynamic>?> checkUpdate() async {
    try {
      final j = await get('/api/version', cache: false);
      final b = (j['build'] ?? 0) as int;
      if (b <= appBuild) return null;
      return {'build': b, 'note': j['note']?.toString() ?? ''};
    } catch (_) {
      return null;
    }
  }
}
