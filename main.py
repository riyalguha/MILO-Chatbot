from fastapi import FastAPI
from fastapi import Request,HTTPException
from fastapi.responses import JSONResponse
import db_helper
import generic_helper

app = FastAPI()


inprogress_order = {}
@app.post("/")
async def handle_request(request: Request):
    # try:    
        payload = await request.json()
        # print("Received payload:", payload)

        intent = payload['queryResult']['intent']['displayName']
        parameters = payload['queryResult']['parameters']
        output_contexts = payload['queryResult']['outputContexts'] 

        session_id = generic_helper.extract_session_id(output_contexts[0]['name'])

        intent_handler_dict = {
             "track.order - context: ongoing-tracking": track_order,
             "order.add - context: ongoing-order": add_to_order,
             "order.complete - context: ongoing-order": complete_order,
             "order.remove - context: ongoing-order": remove_from_order,
        } 

        return intent_handler_dict[intent](parameters,session_id)

def remove_from_order(paramerters:dict, session_id:str):
     if session_id not in inprogress_order:
          return JSONResponse(content={
               "fulfillment_text":"Hey, i am having trouble locating your order. Sorry , Can you please place your order again?"
               })
     else:
          current_order = inprogress_order[session_id]
          food_items = paramerters['food-item']
          removed_items = []
          no_such_items = []

          for item in food_items:
               if item not in current_order:
                    no_such_items.append(item)
               else:
                    removed_items.append(item)
                    del current_order[item]
          
          if len(removed_items) > 0:
               fulfillment_text = f'Removed {",".join(removed_items)} from your ongoing order. '
          if len(no_such_items) > 0:
               fulfillment_text = f'Your current order does not have these items: {",".join(no_such_items)} '

          if len(current_order.keys()) == 0:
               fulfillment_text += "Your order is empty "
          else:
               order_str = generic_helper.get_string_from_food_dict(current_order)
               fulfillment_text += f"Here is what is left in your order: {order_str}"
          
          return JSONResponse(content={"fulfillment_text":fulfillment_text})


def add_to_order(parameters:dict, session_id:str):
     food_items = parameters['food-item']
     quantity = parameters['number']

     if len(food_items) != len(quantity):
          fulfillment_text = "Sorry, I didn't understand that can you please specify your food items and quantity of each food item specifically?.Here is the list opf out menu:Pav Bhaji, Chole Bhature, Pizza, Mango Lassi, Masala Dosa, Biryani, Vada Pav, Rava Dosa, and Samosa."
     else:
          new_food_dict = dict(zip(food_items,quantity))
          if session_id in inprogress_order:
               current_food_dict = inprogress_order[session_id]
               current_food_dict.update(new_food_dict)
               inprogress_order[session_id] = current_food_dict
          else:
               inprogress_order[session_id] = new_food_dict


          order_str = generic_helper.get_string_from_food_dict(inprogress_order[session_id])
          fulfillment_text = f"So far you have {order_str}, Do you need anything else?"

     return JSONResponse(content = {"fulfillment_text":fulfillment_text})

def complete_order(parameters:dict, session_id:str):
     if session_id not in inprogress_order:
          fulfillment_text = "Hey, i am having trouble locating your order. Sorry , Can you please place your order again?"  
     else:
          order = inprogress_order[session_id]
          order_id = save_to_db(order)

          if order_id == -1:
               fulfillment_text = "Sorry, I couldn't process your order due to a backend eror ."\
                                   " Please kindly place a new order again."
          else:
               order_total = db_helper.get_total_order_price(order_id)
               fulfillment_text = f"Awsome i have placed your order "\
                                   f"Here is your order ID {order_id} "\
                                   f"Your order total is {order_total} which you can pay at the time of delivery. "
     

     del inprogress_order[session_id]
     return JSONResponse(content = {"fulfillment_text":fulfillment_text})

def save_to_db(order: dict):
     next_order_id = db_helper.get_next_order_id()

     for food_item, quantity in order.items():
          rcode = db_helper.insert_order_item(
               food_item,
               quantity,
               next_order_id
          )  
          if rcode == -1:
               return -1
          
     db_helper.insert_order_tracking(next_order_id,"in progress")
     return next_order_id

def track_order(parameters:dict,session_id:str):
    order_id = parameters['number']
    order_status = db_helper.get_order_status(order_id)

    if order_status is None:
         fulfillment_text = f"Sorry, The Given order ID does not exist"
    else:
         fulfillment_text = f"The order status for the order ID: {int(order_id)} is: {order_status}"
         

    return JSONResponse(content = {"fulfillment_text":fulfillment_text})
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail = str(e))