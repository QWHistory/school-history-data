export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // 核心逻辑：只要用户访问 /record/ 开头的路径
    if (url.pathname.startsWith('/record/')) {
      // 偷偷去拿 record1.html 的内容
      const response = await env.ASSETS.fetch(new URL('/record1.html', url.origin));
      
      // 把内容丢给浏览器，强制 200 状态码，地址栏绝不改变
      return new Response(response.body, {
        status: 200,
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'no-cache'
        }
      });
    }
    
    // 其他请求（比如首页、archive、css、data.json）正常放行
    return env.ASSETS.fetch(request);
  }
};
