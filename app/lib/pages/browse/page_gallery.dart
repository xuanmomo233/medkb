import 'package:flutter/material.dart';
import '../../api.dart';

String _src(int n) => '${Api.base}/img/page_$n.webp';

class _NetImage extends StatelessWidget {
  final String url;
  final BoxFit fit;
  const _NetImage(this.url, {required this.fit});

  @override
  Widget build(BuildContext context) {
    final Color grey = Theme.of(context).colorScheme.onSurfaceVariant;
    return Image.network(
      url,
      fit: fit,
      loadingBuilder:
          (BuildContext c, Widget child, ImageChunkEvent? progress) {
        if (progress == null) return child;
        return const Center(
          child: SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        );
      },
      errorBuilder: (BuildContext c, Object e, StackTrace? s) =>
          Center(child: Icon(Icons.broken_image_outlined, color: grey)),
    );
  }
}

class PageGallery extends StatelessWidget {
  final List<int> pages;
  const PageGallery({super.key, required this.pages});

  void _open(BuildContext context, int index) {
    Navigator.of(context).push<void>(MaterialPageRoute<void>(
      fullscreenDialog: true,
      builder: (_) => _GalleryViewer(pages: pages, initial: index),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData t = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Text('导图原图',
                style: t.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(width: 8),
            Text('共 ${pages.length} 页',
                style: TextStyle(
                    fontSize: 12, color: t.colorScheme.onSurfaceVariant)),
          ],
        ),
        const SizedBox(height: 12),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 0.78,
          ),
          itemCount: pages.length,
          itemBuilder: (BuildContext c, int i) {
            return InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () => _open(context, i),
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: t.colorScheme.outlineVariant),
                ),
                clipBehavior: Clip.antiAlias,
                child: Stack(
                  fit: StackFit.expand,
                  children: <Widget>[
                    _NetImage(_src(pages[i]), fit: BoxFit.cover),
                    Positioned(
                      right: 4,
                      bottom: 4,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 1),
                        decoration: BoxDecoration(
                          color: Colors.black54,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text('P${pages[i]}',
                            style: const TextStyle(
                                color: Colors.white, fontSize: 11)),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ],
    );
  }
}

class _GalleryViewer extends StatefulWidget {
  final List<int> pages;
  final int initial;
  const _GalleryViewer({required this.pages, required this.initial});

  @override
  State<_GalleryViewer> createState() => _GalleryViewerState();
}

class _GalleryViewerState extends State<_GalleryViewer> {
  late final PageController _pc = PageController(initialPage: widget.initial);
  late int _cur = widget.initial;

  @override
  void dispose() {
    _pc.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text('${_cur + 1} / ${widget.pages.length}'),
      ),
      body: PageView.builder(
        controller: _pc,
        itemCount: widget.pages.length,
        onPageChanged: (int i) => setState(() => _cur = i),
        itemBuilder: (BuildContext c, int i) => InteractiveViewer(
          maxScale: 6,
          child: Center(
            child: _NetImage(_src(widget.pages[i]), fit: BoxFit.contain),
          ),
        ),
      ),
    );
  }
}
