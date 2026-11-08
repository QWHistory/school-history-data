export async function onRequest(context) {
  const url = new URL(context.request.url);
  
  // 构造要请求的静态资源路径 (确保你的根目录有 record.html)
  const assetUrl = new URL('/record.html', url.origin);
  
  // 去静态资源库拉取 record.html 的内容
  const response = await context.env.ASSETS.fetch(assetUrl);

  // 创建一个新的响应，把内容返回给浏览器，但保持原 URL (/record/xxx) 不变
  return new Response(response.body, {
    status: 200,
    headers: response.headers
  });
}
