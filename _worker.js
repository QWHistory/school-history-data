export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    // 把 /record/ 换成 /archives/
    if (url.pathname.startsWith('/archives/')) {
      const response = await env.ASSETS.fetch(new URL('/record1.html', url.origin));
      return new Response(response.body, {
        status: 200,
        headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache' }
      });
    }
    return env.ASSETS.fetch(request);
  }
};
