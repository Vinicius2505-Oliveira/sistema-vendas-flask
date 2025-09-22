from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-secret-change-for-production'

db = SQLAlchemy(app)

# -------------------- MODELS --------------------
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_sale = db.Column(db.Float, nullable=False)

    product = db.relationship('Product')
    order = db.relationship('Order', back_populates='items')

    def subtotal(self):
        return self.quantity * self.price_at_sale

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship('Client')
    items = db.relationship('OrderItem', back_populates='order', cascade='all, delete-orphan')

    def total(self):
        return sum(item.subtotal() for item in self.items)

# -------------------- ROUTES --------------------
@app.route('/')
def index():
    return render_template('index.html',
                           products_count=Product.query.count(),
                           clients_count=Client.query.count(),
                           orders_count=Order.query.count())

# -------------------- PRODUCTS CRUD --------------------
@app.route('/products')
def products():
    return render_template('products.html', products=Product.query.all())

@app.route('/products/new', methods=['GET','POST'])
def product_new():
    if request.method=='POST':
        name=request.form['name'].strip()
        price=float(request.form['price'] or 0)
        stock=int(request.form['stock'] or 0)
        if not name:
            flash('Nome é obrigatório','danger')
            return redirect(url_for('product_new'))
        p=Product(name=name,price=price,stock=stock)
        db.session.add(p)
        db.session.commit()
        flash('Produto criado','success')
        return redirect(url_for('products'))
    return render_template('product_form.html', product=None)

@app.route('/products/<int:product_id>/edit', methods=['GET','POST'])
def product_edit(product_id):
    p=Product.query.get_or_404(product_id)
    if request.method=='POST':
        p.name=request.form['name'].strip()
        p.price=float(request.form['price'] or 0)
        p.stock=int(request.form['stock'] or 0)
        db.session.commit()
        flash('Atualizado','success')
        return redirect(url_for('products'))
    return render_template('product_form.html', product=p)

@app.route('/products/<int:product_id>/delete', methods=['POST'])
def product_delete(product_id):
    p=Product.query.get_or_404(product_id)
    db.session.delete(p)
    db.session.commit()
    flash('Removido','success')
    return redirect(url_for('products'))

# -------------------- CLIENTS CRUD --------------------
@app.route('/clients')
def clients():
    return render_template('clients.html', clients=Client.query.all())

@app.route('/clients/new', methods=['GET','POST'])
def client_new():
    if request.method=='POST':
        name=request.form['name'].strip()
        email=request.form['email'].strip()
        if not name:
            flash('Nome obrigatório','danger')
            return redirect(url_for('client_new'))
        c=Client(name=name,email=email)
        db.session.add(c)
        db.session.commit()
        flash('Cliente criado','success')
        return redirect(url_for('clients'))
    return render_template('client_form.html', client=None)

@app.route('/clients/<int:client_id>/edit', methods=['GET','POST'])
def client_edit(client_id):
    c=Client.query.get_or_404(client_id)
    if request.method=='POST':
        c.name=request.form['name'].strip()
        c.email=request.form['email'].strip()
        db.session.commit()
        flash('Atualizado','success')
        return redirect(url_for('clients'))
    return render_template('client_form.html', client=c)

@app.route('/clients/<int:client_id>/delete', methods=['POST'])
def client_delete(client_id):
    c=Client.query.get_or_404(client_id)
    db.session.delete(c)
    db.session.commit()
    flash('Removido','success')
    return redirect(url_for('clients'))

# -------------------- ORDERS --------------------
@app.route('/orders')
def orders():
    return render_template('orders.html', orders=Order.query.order_by(Order.created_at.desc()).all())

@app.route('/orders/new', methods=['GET','POST'])
def order_new():
    products = Product.query.filter(Product.stock > 0).all()
    clients = Client.query.all()
    if request.method == 'POST':
        client_id = int(request.form['client_id'])
        client = Client.query.get_or_404(client_id)
        order = Order(client=client)
        db.session.add(order)

        for p in products:
            qty = int(request.form.get(f'product_{p.id}', '0') or 0)
            if qty > 0:
                if qty <= p.stock:
                    item = OrderItem(product=p, quantity=qty, price_at_sale=p.price)
                    order.items.append(item)  # associa o item ao pedido
                    p.stock -= qty
                    db.session.add(item)
                else:
                    flash(f'Estoque insuficiente para {p.name}', 'danger')
                    db.session.rollback()
                    return redirect(url_for('order_new'))

        db.session.commit()
        flash('Pedido criado', 'success')
        return redirect(url_for('orders'))

    return render_template('order_form.html', products=products, clients=clients)

@app.route('/orders/<int:order_id>')
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order_detail.html', order=order)

@app.route('/orders/<int:order_id>/delete', methods=['POST'])
def order_delete(order_id):
    order = Order.query.get_or_404(order_id)
    for item in order.items:
        prod = Product.query.get(item.product_id)
        if prod:
            prod.stock += item.quantity
    db.session.delete(order)
    db.session.commit()
    flash('Pedido removido e estoque restaurado', 'success')
    return redirect(url_for('orders'))

# -------------------- MAIN --------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
