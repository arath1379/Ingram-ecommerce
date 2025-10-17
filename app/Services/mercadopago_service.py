import mercadopago
import os
import json

class MercadoPagoService:
    def __init__(self):
        # Obtener credenciales REALES
        try:
            from flask import current_app
            self.access_token = current_app.config.get('MERCADOPAGO_ACCESS_TOKEN')
        except:
            self.access_token = None
            
        if not self.access_token:
            self.access_token = os.environ.get('MERCADOPAGO_ACCESS_TOKEN')
            
        if not self.access_token:
            print("❌ ERROR: MERCADOPAGO_ACCESS_TOKEN no configurada")
            print("💡 Solución: Agrega MERCADOPAGO_ACCESS_TOKEN a tu archivo .env")
            print("💡 Ve a: https://www.mercadopago.com.mx/developers/panel")
            raise ValueError("MERCADOPAGO_ACCESS_TOKEN no configurada")
        
        print(f"🔑 Token MP configurado: {self.access_token[:30]}...")
        self.sdk = mercadopago.SDK(self.access_token)

    # En MercadoPagoService - VERSIÓN SIMPLIFICADA
    def create_preference(self, cart_data, user_email, success_url, failure_url, pending_url, user_name=None):
        """Crear preferencia con datos reales - SIN auto_return"""
        try:
            print("🎯 Creando preferencia MP con credenciales reales...")
            print(f"💰 Total: ${cart_data['total_amount']} MXN")
            print(f"📧 Cliente: {user_email}")
            
            # VERIFICAR URLs de forma más estricta
            if not success_url or not success_url.startswith('http'):
                raise ValueError(f"URL de éxito inválida: {success_url}")
            
            print(f"🔗 Success URL: {success_url}")
            print(f"🔗 Failure URL: {failure_url}")
            print(f"🔗 Pending URL: {pending_url}")
            
            # Preferencia SIN auto_return
            preference_data = {
                "items": [
                    {
                        "id": "compra-itdata",
                        "title": f"Compra IT Data Global - {cart_data['order_number']}",
                        "description": f"Compra de {len(cart_data['items'])} productos tecnológicos",
                        "quantity": 1,
                        "currency_id": "MXN",
                        "unit_price": float(cart_data['total_amount'])
                    }
                ],
                "payer": {
                    "email": user_email,
                    "name": user_name or "Cliente"
                },
                "back_urls": {
                    "success": success_url,
                    "failure": failure_url, 
                    "pending": pending_url
                },
                # REMOVEMOS auto_return completamente
                "external_reference": cart_data['order_number'],
                "statement_descriptor": "ITDATA GLOBAL"
            }

            print("📤 Enviando a MercadoPago...")
            result = self.sdk.preference().create(preference_data)
            
            print(f"📨 Status MP: {result.get('status')}")
            
            if result.get("status") in [200, 201]:
                preference = result.get("response", {})
                
                if "id" in preference:
                    init_point = preference.get('init_point') or preference.get('sandbox_init_point')
                    print(f"✅ ÉXITO - Preferencia creada: {preference['id']}")
                    print(f"🔗 URL de pago: {init_point}")
                    
                    return {
                        'success': True,
                        'preference_id': preference['id'],
                        'init_point': init_point
                    }
                else:
                    return {'success': False, 'error': 'No se recibió ID de preferencia'}
            else:
                error_msg = result.get('message', 'Error desconocido en MercadoPago')
                error_details = result.get('response', {})
                print(f"❌ Error MP: {error_msg}")
                print(f"🔍 Detalles: {error_details}")
                return {'success': False, 'error': f'{error_msg}: {error_details}'}
                
        except Exception as e:
            print(f"❌ Excepción en MP: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}