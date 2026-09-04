from app.config.database import get_database
from datetime import datetime


db = get_database()



def save_planner_result(
    student_id,
    result
):

    collection = db["planner_results"]


    document = {"student_id": student_id, "generated_at": datetime.now(), **result}


    collection.update_one(

        {
            "student_id": student_id
        },

        {
            "$set": document
        },

        upsert=True

    )





def get_latest_plan(
    student_id
):

    collection = db["planner_results"]


    result = collection.find_one(
        {
            "student_id": student_id
        }
    )


    if result:

        result["_id"] = str(
            result["_id"]
        )


    return result
