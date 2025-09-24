analytics_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_data_from_database",
            "description": "Make an SQL query to a database to get relevant data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Textual description of what you are trying to find or what are you doing"
                    },
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute"
                    }
                },
                "required": [
                    "description",
                    "query",
                ],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_graph",
            "description": "Send graph data to the frontend for plotting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x_label": {"type": "string", "description": "Label for the X axis"},
                    "y_label": {"type": "string", "description": "Label for the Y axis"},
                    "x_coordinates": {"type": "array", "items": {"type": "string"}, "description": "X axis values"},
                    "y_coordinates": {"type": "array", "items": {"type": "number"}, "description": "Y axis values"}
                },
                "required": ["x_label", "y_label", "x_coordinates", "y_coordinates"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_bar_graph",
            "description": "Send bar graph data to the frontend for plotting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x_label": {"type": "string", "description": "Label for the X axis"},
                    "y_label": {"type": "string", "description": "Label for the Y axis"},
                    "x_coordinates": {"type": "array", "items": {"type": "string"}, "description": "X axis values"},
                    "y_coordinates": {"type": "array", "items": {"type": "number"}, "description": "Y axis values"},
                    "legend": {"type": "string", "description": "Legend for the bar graph"},
                    "description": {"type": "string", "description": "Description for the graph"}
                },
                "required": ["x_label", "y_label", "x_coordinates", "y_coordinates", "legend", "description"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_line_graph",
            "description": "Send line graph data to the frontend for plotting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x_label": {"type": "string", "description": "Label for the X axis"},
                    "y_label": {"type": "string", "description": "Label for the Y axis"},
                    "x_coordinates": {"type": "array", "items": {"type": "string"}, "description": "X axis values"},
                    "y_coordinates": {"type": "array", "items": {"type": "number"}, "description": "Y axis values"},
                    "legend": {"type": "string", "description": "Legend for the line graph"},
                    "description": {"type": "string", "description": "Description for the graph"}
                },
                "required": ["x_label", "y_label", "x_coordinates", "y_coordinates", "legend", "description"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_area_graph",
            "description": "Send area graph data to the frontend for plotting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x_label": {"type": "string", "description": "Label for the X axis"},
                    "y_label": {"type": "string", "description": "Label for the Y axis"},
                    "x_coordinates": {"type": "array", "items": {"type": "string"}, "description": "X axis values"},
                    "y_coordinates": {"type": "array", "items": {"type": "number"}, "description": "Y axis values"},
                    "legend": {"type": "string", "description": "Legend for the area graph"},
                    "description": {"type": "string", "description": "Description for the graph"}
                },
                "required": ["x_label", "y_label", "x_coordinates", "y_coordinates", "legend", "description"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_doughnut_graph",
            "description": "Send doughnut chart data to the frontend for plotting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels for each segment"},
                    "values": {"type": "array", "items": {"type": "number"}, "description": "Values for each segment"},
                    "legend": {"type": "string", "description": "Legend for the doughnut chart"},
                    "description": {"type": "string", "description": "Description for the chart"}
                },
                "required": ["labels", "values", "legend", "description"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
]


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "refine_query",
            "description": "refine the user query to be more specific and relevant so that you can answer it better",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The original user query that needs refinement"
                    },
                    "context": {
                        "type": "string",
                        "description": "conversation context to help refine the query"
                    }
                },
                "required": ["query", "context"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_data_from_excel",
            "description": "gets data from an excel file using python with pandas ",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "ID of the Excel file to query"
                    },
                    "pandas_query": {
                        "type": "string",
                        "description": "python code using pandas to get the information user wants "
                    }
                },
                "required": ["file_id", "pandas_query"],
                "additionalProperties": False
            },
        }
    },
]

# INTEGRATION_TOOLS = [
#     {
#         "type": "function",
#         "function": {
#             "name": "order_tracking_with_order_id",
#             "description": "Get the Shopify order status using a provided order ID.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "order_id": {
#                         "type": "string",
#                         "description": "The order ID for the specific order"
#                     },
#                 },
#                 "required": ["order_id"],
#                 "additionalProperties": False
#             }
#         }
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "get_shopify_orders",
#             "description": "Use this to fetch the user's Shopify orders when they ask about their orders e.g 'tell me about my latest orders','my orders'.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {},
#                 "required": [],
#                 "additionalProperties": False
#             }
#         }
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "return_processing",
#             "description": "Initiate and process a return for a Shopify order using the provided order ID.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "order_name": {
#                         "type": "string",
#                         "description": "The Shopify order ID (e.g., '#CH1234567') to initiate a return for."
#                     },
#                     "return_reason": {
#                         "type": "string",
#                         "description": "The reason for the return. Valid values: 'DAMAGED', 'DEFECTIVE', 'TOO_SMALL', 'TOO_LARGE', 'NOT_AS_DESCRIBED', 'OTHER'. Default is 'OTHER'.",
#                         "default": "OTHER"
#                     }
#                 },
#                 "required": ["order_name"],
#                 "additionalProperties": False
#             }
#         }
#     },
#     # {
#     #     "type": "function",
#     #     "function": {
#     #         "name": "list_of_orders_with_customer_phone_number",
#     #         "description": "Get all Shopify orders linked to a customer's phone number.",
#     #         "parameters": {
#     #             "type": "object",
#     #             "properties": {
#     #                 "phone_number": {
#     #                     "type": "string",
#     #                     "description": "The phone number associated with the order"
#     #                 },
#     #             },
#     #             "required": ["phone_number"],
#     #             "additionalProperties": False
#     #         }
#     #     }
#     # },
#     {
#         "type": "function",
#         "function": {
#             "name": "get_product_recommendations",
#             "description": "Recommend relevant products to the user based on their query or interest.",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "query": {
#                         "type": "string",
#                         "description": "The user's shopping query, e.g., 'smartphone under 500', 'laptop for video editing'"
#                     }
#                 },
#                 "required": ["query"],
#                 "additionalProperties": False
#             }
#         }
#     }
# ]

INTEGRATION_TOOLS = {
    "1001": {
        "type": "function",
        "function": {
            "name": "order_tracking_with_order_id",
            "description": "Get the Shopify order status using a provided order ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID for the specific order"
                    },
                },
                "required": ["order_id"],
                "additionalProperties": False
            }
        }
    },
    "1002": {
        "type": "function",
        "function": {
            "name": "get_shopify_orders",
            "description": "Use this to fetch the user's Shopify orders when they ask about their orders e.g 'tell me about my latest orders','my orders'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            }
        }
    },
    "1003": {
        "type": "function",
        "function": {
            "name": "return_processing",
            "description": "Initiate and process a return for a Shopify order using the provided order ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_name": {
                        "type": "string",
                        "description": "The Shopify order ID (e.g., '#CH1234567') to initiate a return for."
                    },
                    "return_reason": {
                        "type": "string",
                        "description": "The reason for the return. Valid values: 'DAMAGED', 'DEFECTIVE', 'TOO_SMALL', 'TOO_LARGE', 'NOT_AS_DESCRIBED', 'OTHER'. Default is 'OTHER'.",
                        "default": "OTHER"
                    }
                },
                "required": ["order_name"],
                "additionalProperties": False
            }
        }
    },
    "1004": {
        "type": "function",
        "function": {
            "name": "get_product_recommendations",
            "description": "Recommend relevant products to the user based on their query or interest.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's shopping query, e.g., 'smartphone under 500', 'laptop for video editing'"
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        }
    }
}

WEBHOOK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_relevant_images",
            "description": "Retrieve relevant image URLs based on context of conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "The user query and context of conversation to find relevant images."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of images to return (cannot be more than 5).",
                        "default": 5
                    },
                    "board_id": {
                        "type": "string",
                        "description": "id of the board where the images are stored."
                    }
                },
                "required": ["context", "max_results", "board_id"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_user_data",
            "description": "Capture user data during the conversation which was asked to capture from the conversation.capture the data from the user and store it in the chat room. like @phone_number, @email, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_to_capture": {
                        "type": "object",
                        "description": "Data to capture from user interactions, structured as key-value pairs.",
                        "additionalProperties": {
                            "type": "string"
                        }
                    },
                    "room_id": {
                        "type": "string",
                        "description": "The uuid of the chat room where the data is being captured. given as room_id or session_id in the system prompt."
                    }
                },
                "required": ["data_to_capture", "room_id"],
                "additionalProperties": True
            },
            "strict": False
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_buttons",
            "description": "returns buttons based on the context of the conversation. ",
            "parameters": {
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "The context of the conversation to generate buttons."
                    },
                    "max_buttons": {
                        "type": "integer",
                        "description": "Maximum number of buttons to return (cannot be more than 5).",
                        "default": 5
                    }
                }
            }
        }
    }

]


IMAGES = [  # example images for tools to show, modify this accordingly
    {
        'url': "https://imgd.aeplcdn.com/642x336/n/cw/ec/20865/amg-gt-exterior-right-front-three-quarter-60800.jpeg?q=80",
        'metadata': {
            'title': "mercedes amg gt",
            'description': "A high-performance sports car with a sleek design and powerful engine."
        }
    },
    {
        'url': "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQm33ep5S-KcyUq_bdFTZdVhUqF-SQ1UamgWA&s",
        'metadata': {
            'title': "mercedes benz luxury",
            'description': "A luxury car brand known for its high-quality vehicles and advanced technology."
        }
    }]

BUTTONS = [
    {
        "content": "Book Test Drive",
        "description": "Schedule a test drive for the car you are interested in.",
    },
    {
        "content": "Don't book a Test Drive",
        "description": "Choose not to book a test drive at this time.",
    }
]
