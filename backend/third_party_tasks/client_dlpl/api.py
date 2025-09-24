from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
import requests
from backend.settings import logger
from .utils import (
    get_auth_token,
    get_order_amount,
    get_order_id
)
from .constants import (
    PAYMENT_URL,
    X_API_KEY,
    PATIENT_FAMILY_URL,
    PATIENT_ADDRESSES_URL,
    X_API_KEY1
)
import json

class PatientFamily(APIView):

    def get(self, request):
        try:
            logger.info(f"PatientFamily GET data {request.query_params}")
            custom_data_source = request.query_params.get("custom_data_source",7)
            page = request.query_params.get("page",1)
            size = request.query_params.get("size",10)
            phone_number = request.query_params.get("phone_number")
            session_id = request.query_params.get("session_id")

            auth_token = get_auth_token(session_id=session_id)
            logger.debug(f"=======================Auth Token: {auth_token}")
            if not auth_token:
                return Response(
                    {
                        "status":"error",
                        "error_message":"Please Login"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            url = PATIENT_FAMILY_URL
            
            payload ={
                "auth_code": auth_token,
                "page": int(page),
                "size": int(size),
                "phone_number": phone_number,
                "custom_data": {
                    "source": int(custom_data_source)
                }
            }

            headers = {
                "x-api-key": X_API_KEY,
                "Content-Type": "application/json"
            }

            logger.info(f"PatientFamily {payload}")
            response = requests.post(
                url=url,
                data=json.dumps(payload),
                headers=headers
            )
            logger.debug(f"=-=-=--=-=-=-=-=-=-=-=-=-=-Response from PatientFamily: {response}, {response.text}, {response.status_code}, {response.json()}, {response.content}")
            if response.ok:
                return Response(
                    response.json(), 
                    status=response.status_code
                )
            else:
                return Response(
                    response.json(), 
                    status=response.status_code
                )

        except Exception as e:
            logger.error(f"Error PatientFamily {e}")
            return Response(
                    {
                        "status":"error",
                        "error_message":f"Error PatientFamily {e}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )


class PatientAddresses(APIView):
    def get(self, request):
        try:
            logger.info(f"PatientAddresses GET data {request.query_params}")
            custom_data_source = request.query_params.get("custom_data_source",7)
            phone_number = request.query_params.get("phone_number")
            session_id = request.query_params.get("session_id")
            patient_id = request.query_params.get("patient_id")
            # state_name =  request.query_params.get("state_name")
            # city_name = request.query_params.get("city_name")

            auth_token = get_auth_token(session_id=session_id)

            if not auth_token:
                return Response(
                    {
                        "status":"error",
                        "error_message":"Please Login"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            url = PATIENT_ADDRESSES_URL
            
            payload ={
                "auth_code": auth_token,
                "phone_number": phone_number,
                "custom_data": {
                    "source": custom_data_source
                },
                # "state_name": state_name,
                # "city_name": city_name,
                "auth_id": patient_id
            }

            headers = {
                "x-api-key": X_API_KEY,
                "Content-Type": "application/json"
            }

            logger.info(f"PatientAddresses {payload}")
            response = requests.post(
                url=url,
                data=json.dumps(payload),
                headers=headers
            )

            if response.ok:
                return Response(
                    response.json(), 
                    status=response.status_code
                )
            else:
                return Response(
                    response.json(), 
                    status=response.status_code
                )

        except Exception as e:
            logger.error(f"Error PatientAddresses {e}")
            return Response(
                    {
                        "status":"error",
                        "error_message":f"Error PatientAddresses {e}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

class ReportStatusByLabNo(APIView):
    def get(self, request):
        try:
            logger.info(f"ReportStatusByLabNo GET data {request.query_params}")
            lab_no = request.query_params.get("LabNo")

            if not lab_no:
                return Response(
                    {
                        "status": "error",
                        "error_message": "LabNo is required"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            url = f"https://1xviewapiintegration.lalpathlabs.com/v1/chatbot/report-status/{lab_no}"

            headers = {
                "x-api-key": "a7698976-ec8c-4bac-8cae-4be203981fc3",
                "Content-Type": "application/json"
            }

            response = requests.get(url=url, headers=headers)
            res_data = response.json()

            
            if response.status_code == 400:
                message = res_data.get("message", "")
                error_data = res_data.get("error", {})

                
                if "ETR NOT FOUND" in error_data.get("message", ""):
                    return Response(
                        {
                            "LabNo": error_data.get("lab_number"),
                            "scenario": "etr_not_found",
                            "message": message
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if "Invalid labnumber" in message:
                    return Response(
                        {
                            "LabNo": None,
                            "scenario": "invalid_lab_number",
                            "message": message
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if "CANCELLED" in message:
                    return Response(
                        {
                            "LabNo": None,
                            "scenario": "order_cancelled",
                            "message": message
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                return Response(res_data, status=status.HTTP_400_BAD_REQUEST)

            data = res_data.get("data", {})
            etr = data.get("etr", [])
            is_within_etr = data.get("is_within_etr")
            report_link = data.get("report_link")
            has_released_report = any(
                t.get("report_release_status") for t in etr if t.get("report_release_status")
            )

            if report_link:
                scenario = "final_report_ready"
            elif is_within_etr and all(t.get("is_within_etr") for t in etr):
                scenario = "all_within_etr"
            elif not is_within_etr and all(not t.get("is_within_etr") for t in etr):
                scenario = "all_outside_etr"
            elif not is_within_etr and any(t.get("is_within_etr") for t in etr):
                scenario = "partial_within_etr"
            elif has_released_report and is_within_etr:
                scenario = "interim_released_all_within_etr"
            elif has_released_report and not is_within_etr:
                scenario = "interim_released_partial_outside_etr"
            else:
                scenario = "unknown_case"
            logger.debug(f"ReportStatusByLabNo scenario: {scenario}")
            wrapper_response = {
                "LabNo": data.get("lab_number"),
                "message": data.get("message"),
                "report_link": report_link,
                "tests": etr
            }

            return Response(wrapper_response, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error ReportStatusByLabNo {e}")
            return Response(
                {
                    "status": "error",
                    "error_message": f"Error ReportStatusByLabNo {e}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
class RedirectToShortUrl(APIView):
   def post(self, request):
       try:
           session_id = request.data.get("session_id")
           phone_number = request.query_params.get("phone_number")
           order_id = get_order_id(session_id=session_id)
           order_amount = get_order_amount(session_id=session_id)
           auth_token = get_auth_token(session_id=session_id)


           payload = {
               "auth_code": auth_token,
               "order_id":order_id,
               "order_net_amount":order_amount,
               "phone_number": phone_number,
           }
           # External API URL
           external_api_url = PAYMENT_URL

           headers = {
               "x-api-key": X_API_KEY,
               "Content-Type": "application/json"
           }
           # Forward request to external API
           response = requests.post(external_api_url, headers=headers, json=payload, timeout=20)
           if response.status_code != 200:
               return Response(
                   {"error": "Failed to fetch URL"},
                   status=response.status_code,
               )
           api_data = response.json()
           # Extract short_url
           short_url = api_data.get("data", {}).get("short_url")
           logger.info(f"---short url to redirect is----{short_url}")
           if not short_url:
               return Response({"error": "No short_url found"}, status=400)
           # Redirect to short_url
           return (f"url for payment{short_url}")
       except Exception as e:
           return Response({"error": str(e)}, status=500)
