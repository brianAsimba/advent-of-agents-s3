"""Fake shop service on main. Contract: create_app(conn, shell); the signed-in user arrives in the X-User header."""
from flask import Flask, abort, jsonify


def create_app(conn, shell):
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/products/<int:product_id>")
    def product(product_id):
        row = conn.execute("SELECT name FROM products WHERE id = ?", (product_id,)).fetchone()
        return jsonify(name=row[0]) if row else abort(404)

    return app
