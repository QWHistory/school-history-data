export async function onRequest(context) {
  const url = new URL(context.request.url);
  // 在服务器底层直接提取 record.html 内容，但浏览器地址栏原封不动保留 /record/数字
  const newUrl = new URL('/record.html', url.origin);
  return context.env.ASSETS.fetch(new Request(newUrl, context.request));
}
