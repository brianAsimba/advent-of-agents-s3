"""What a correct patch of sample/pr_app.py looks like. Used as the fake model's reply in tests."""
from html import escape

from flask import Flask, abort, jsonify, request


def create_app(conn, shell):
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/products/<int:product_id>")
    def product(product_id):
        row = conn.execute("SELECT name FROM products WHERE id = ?", (product_id,)).fetchone()
        return jsonify(name=row[0]) if row else abort(404)

    @app.get("/search")
    def search():
        q = request.args.get("q", "")
        rows = conn.execute("SELECT name FROM products WHERE name LIKE ?", (f"%{q}%",)).fetchall()
        return jsonify(results=[r[0] for r in rows])

    @app.get("/ping")
    def ping():
        return jsonify(output=shell(["ping", "-c", "1", request.args.get("host", "")]))

    @app.get("/hello")
    def hello():
        return f"<h1>Hello {escape(request.args.get('name', 'there'))}</h1>"

    @app.get("/invoices/<int:invoice_id>")
    def invoice(invoice_id):
        row = conn.execute("SELECT owner, memo FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not row or row[0] != request.headers.get("X-User"):
            abort(404)
        return jsonify(owner=row[0], memo=row[1])

    return app
