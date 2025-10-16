import stripe
import os

class StripePaymentService:
    def __init__(self):
        # Intentar obtener de config primero, luego de variables de entorno
        try:
            from flask import current_app
            self.stripe_api_key = current_app.config.get('STRIPE_SECRET_KEY')
        except:
            self.stripe_api_key = None
            
        # Si no está en config, buscar en variables de entorno
        if not self.stripe_api_key:
            self.stripe_api_key = os.environ.get('STRIPE_SECRET_KEY')
            
        # Si aún no hay clave, usar una temporal para pruebas
        if not self.stripe_api_key:
            print("⚠️  STRIPE_SECRET_KEY no encontrada. Usando clave de prueba...")
            # Esta es una clave de prueba de Stripe - NO usar en producción
            self.stripe_api_key = "sk_test_4eC39HqLyjWDarjtT1zdp7dc"
        
        if not self.stripe_api_key:
            raise ValueError("STRIPE_SECRET_KEY no está configurada")
        
        stripe.api_key = self.stripe_api_key
        print(f"✅ Stripe configurado con clave: {self.stripe_api_key[:20]}...")

    def create_payment_link(self, cart_data, user_email, success_url, cancel_url):
        """Crear link de pago único para el carrito"""
        try:
            print(f"🎯 Creando payment link para: {cart_data['order_number']}")
            print(f"💰 Total: ${cart_data['total_amount']} MXN")
            
            # Crear producto
            product_name = f"Compra IT Data Global - {cart_data['order_number']}"
            if len(product_name) > 40:
                product_name = product_name[:40]
            
            product = stripe.Product.create(name=product_name)
            print(f"✅ Producto creado: {product.id}")
            
            # Crear precio (Stripe usa centavos)
            price_amount = int(cart_data['total_amount'] * 100)
            
            price = stripe.Price.create(
                product=product.id,
                unit_amount=price_amount,
                currency='mxn',
            )
            print(f"✅ Precio creado: ${cart_data['total_amount']} MXN")
            
            # Crear link de pago
            payment_link = stripe.PaymentLink.create(
                line_items=[{
                    'price': price.id,
                    'quantity': 1,
                }],
                after_completion={
                    'type': 'redirect',
                    'redirect': {
                        'url': success_url
                    }
                }
            )
            
            print(f"✅ Payment link creado: {payment_link.url}")
            
            return {
                'success': True,
                'payment_url': payment_link.url,
                'payment_id': payment_link.id
            }
            
        except stripe.error.StripeError as e:
            error_msg = f"Error de Stripe: {str(e)}"
            print(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
        except Exception as e:
            error_msg = f"Error general: {str(e)}"
            print(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}