from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


HOST = "127.0.0.1"
PORT = 8787


class CheckoutPageHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/checkout/success":
            session_id = parse_qs(parsed.query).get("session_id", ["cs_test_preview"])[0]
            self._send_page(
                title="Order confirmed",
                heading="Order confirmed",
                body=(
                    "AgriBroker received the Stripe Checkout return. "
                    "Return to ASI:One and send: I paid. AgriBroker will verify Stripe "
                    "and then release the farm payout receipt."
                ),
                detail=f"Checkout session: {session_id}",
                accent="#0a7c48",
            )
            return

        if parsed.path == "/checkout/cancel":
            self._send_page(
                title="Checkout canceled",
                heading="Checkout canceled",
                body="The Stripe Checkout flow was canceled. No buyer funding was confirmed.",
                detail="Return to ASI:One and run the procurement request again.",
                accent="#9a3412",
            )
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_page(
        self,
        *,
        title: str,
        heading: str,
        body: str,
        detail: str,
        accent: str,
    ) -> None:
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f7f9;
      color: #17202a;
    }}
    main {{
      width: min(560px, calc(100vw - 32px));
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 32px;
      box-shadow: 0 18px 50px rgba(15, 23, 42, 0.12);
    }}
    .mark {{
      width: 48px;
      height: 48px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      background: {accent};
      color: white;
      font-weight: 800;
      margin-bottom: 20px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    p {{
      margin: 0 0 18px;
      line-height: 1.5;
      color: #4b5563;
    }}
    code {{
      display: block;
      padding: 12px;
      background: #f3f4f6;
      border-radius: 6px;
      overflow-wrap: anywhere;
      color: #111827;
    }}
  </style>
</head>
<body>
  <main>
    <div class="mark">✓</div>
    <h1>{heading}</h1>
    <p>{body}</p>
    <code>{detail}</code>
  </main>
</body>
</html>"""
        body_bytes = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), CheckoutPageHandler)
    print(f"Serving AgriBroker checkout pages at http://{HOST}:{PORT}")
    print("Success URL: http://127.0.0.1:8787/checkout/success?session_id={CHECKOUT_SESSION_ID}")
    print("Cancel URL:  http://127.0.0.1:8787/checkout/cancel")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AgriBroker checkout page server.")


if __name__ == "__main__":
    main()
