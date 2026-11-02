DOCS_UNAVAILABLE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Docs under construction | Plan2World</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center;
      padding: 24px; background: #f7f8f2; color: #23332c;
      font-family: "Segoe UI", Arial, sans-serif; text-align: center; }
    main { width: min(100%, 560px); }
    .badge { font-size: 11px; letter-spacing: 2px; color: #678052; }
    h1 { font-size: clamp(32px, 7vw, 48px); letter-spacing: -2px; margin: 24px 0 16px; }
    p { line-height: 1.8; color: #66745f; }
    .site { position: relative; height: 150px; margin: 30px auto; max-width: 320px;
      border-bottom: 5px solid #273f30; overflow: hidden; }
    .brick { position: absolute; width: 58px; height: 28px; border: 3px solid #f7f8f2;
      border-radius: 4px; background: #7d9772; bottom: 0; left: 80px; }
    .brick:nth-child(2) { left: 138px; }
    .brick:nth-child(3) { left: 109px; bottom: 28px; }
    .brick:nth-child(4) { left: 167px; bottom: 28px; }
    .brick:nth-child(5) { left: 138px; bottom: 56px; background: #c4552f;
      animation: build 2s ease-in-out infinite; }
    @keyframes build {
      0%, 100% { transform: translateY(-60px) rotate(-12deg); }
      50%, 70% { transform: translateY(0) rotate(0); }
    }
    a { display: inline-block; margin-top: 20px; padding: 14px 22px;
      border-radius: 5px; background: #273f30; color: #fff; text-decoration: none; }
    a:focus-visible { outline: 3px solid #c4552f; outline-offset: 5px; }
    small { display: block; margin-top: 28px; color: #7b8376; }
    @media (prefers-reduced-motion: reduce) { .brick:nth-child(5) { animation: none; } }
  </style>
</head>
<body>
  <main>
    <span class="badge">PLAN2WORLD / DOCS DEPARTMENT</span>
    <div class="site" aria-hidden="true">
      <span class="brick"></span><span class="brick"></span><span class="brick"></span>
      <span class="brick"></span><span class="brick"></span>
    </div>
    <h1>Our docs are laying low.</h1>
    <p>We're working on it! The tiny construction crew insists on
      measuring every pixel twice. Apparently the coffee machine is a load-bearing wall.</p>
    <a href="/">Back to Plan2World</a>
    <small>No blueprints were harmed in the making of this page.</small>
  </main>
</body>
</html>
"""
