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

    def create_preference(self, cart_data, user_email, success_url, failure_url, pending_url, user_name=None):
        """Crear preferencia con datos reales - VERSIÓN SIMPLIFICADA Y CORREGIDA"""
        try:
            print("🎯 Creando preferencia MP - VERSIÓN SIMPLIFICADA...")
            print(f"💰 Total con IVA: ${cart_data['total_amount']} MXN")
            print(f"📊 Subtotal: ${cart_data['subtotal']:.2f}, IVA: ${cart_data['tax_amount']:.2f}")
            print(f"📧 Cliente: {user_email}")
            print(f"📦 Items en carrito: {len(cart_data['items'])}")
            
            # VERIFICAR URLs críticamente
            if not success_url or not success_url.startswith('http'):
                print(f"❌ URL de éxito inválida: {success_url}")
                # Crear una URL de éxito por defecto
                base_url = "http://192.168.1.62:5000"
                success_url = f"{base_url}/payment/mercadopago/success"
                failure_url = f"{base_url}/payment/mercadopago/failure"
                pending_url = f"{base_url}/payment/mercadopago/pending"
                print(f"🔄 Usando URLs por defecto: {success_url}")
            
            print(f"🔗 Success URL: {success_url}")
            print(f"🔗 Failure URL: {failure_url}")
            print(f"🔗 Pending URL: {pending_url}")
            
            # CREAR ITEMS DETALLADOS
            mp_items = []
            
            for item in cart_data['items']:
                product = item['product']
                unit_price = float(item['unit_price'])
                quantity = int(item['quantity'])
                
                mp_item = {
                    "id": product['ingramPartNumber'],
                    "title": f"{product['vendorName']} - {product['description'][:50]}...",
                    "description": product['description'][:100],
                    "quantity": quantity,
                    "currency_id": "MXN",
                    "unit_price": unit_price
                }
                mp_items.append(mp_item)
                print(f"📦 Item: {product['ingramPartNumber']} - {quantity} x ${unit_price:.2f}")
            
            # AGREGAR EL IVA COMO ITEM SEPARADO
            tax_amount = float(cart_data['tax_amount'])
            if tax_amount > 0:
                mp_items.append({
                    "id": "iva-16",
                    "title": "IVA (16%)",
                    "description": "Impuesto al Valor Agregado",
                    "quantity": 1,
                    "currency_id": "MXN", 
                    "unit_price": tax_amount
                })
                print(f"💰 IVA: ${tax_amount:.2f}")
            
            print(f"✅ Total final: ${cart_data['total_amount']:.2f}")

            # PREFERENCIA MUY SIMPLIFICADA - SIN auto_return NI notification_url
            preference_data = {
                "items": mp_items,
                "payer": {
                    "email": user_email,
                    "name": user_name or "Cliente"
                },
                "back_urls": {
                    "success": success_url,
                    "failure": failure_url, 
                    "pending": pending_url
                },
                "external_reference": cart_data['order_number'],
                "statement_descriptor": "ITDATA GLOBAL"
                # REMOVEMOS completamente auto_return y notification_url por ahora
            }

            print("📤 Enviando preferencia simplificada a MercadoPago...")
            print(f"📋 Datos de la preferencia: {json.dumps(preference_data, indent=2)}")
            
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
                        'init_point': init_point,
                        'amounts': {
                            'subtotal': cart_data['subtotal'],
                            'tax_amount': cart_data['tax_amount'],
                            'total_amount': cart_data['total_amount']
                        }
                    }
                else:
                    error_msg = "No se recibió ID de preferencia en la respuesta"
                    print(f"❌ {error_msg}")
                    return {'success': False, 'error': error_msg}
            else:
                error_msg = result.get('message', 'Error desconocido en MercadoPago')
                error_details = result.get('response', {})
                print(f"❌ Error MP: {error_msg}")
                print(f"🔍 Detalles completos: {error_details}")
                
                # Información más detallada del error
                if 'cause' in error_details:
                    print(f"🔍 Causa: {error_details['cause']}")
                
                return {'success': False, 'error': f'{error_msg}: {error_details}'}
                
        except Exception as e:
            print(f"❌ Excepción en MP: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': f'Error al crear preferencia: {str(e)}'}