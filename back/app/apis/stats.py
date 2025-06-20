from flask import Blueprint, jsonify, send_file, request
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.sql import func
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io

from .. import db
from ..models import TrackedTime


stats = Blueprint("stats", __name__)

@stats.route("/get-disk-diagram-for-today", methods=["GET"])
def get_disk_diagram():
    try:
        # Get today's date
        today = datetime.now(ZoneInfo('Europe/Chisinau')).date()
        time_differences = db.session.query(
            func.sum(
                func.extract('epoch', TrackedTime.end_time) -
                func.extract('epoch', TrackedTime.start_time)
            )
        ).filter(
            func.date(TrackedTime.start_time) == today
        ).scalar()
        if not time_differences: 
            return jsonify({"msg": "No data!"}), 404
        work_time_in_hours = (time_differences/60)/60

        # Plot
        labels = ['Worked Time', 'Remaining Time']
        sizes = [work_time_in_hours, max(12 - work_time_in_hours, 0)]
        colors = ['#66b3ff', '#ff9999']
        explode = (0.01, 0)

        plt.figure(figsize=(6, 6))
        plt.pie(sizes, explode=explode, labels=labels, colors=colors,  
                autopct=lambda p: f"{p:.1f}%\n({p * sum(sizes) / 100:.1f} hrs)", startangle=140)
        plt.axis('equal')
        plt.title(today)

        # Save the plot to a BytesIO object
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        plt.close()

        # Return the plot
        return send_file(img, mimetype='image/png')
    except:
        traceback.print_exc()
        return jsonify({"error": "An error occurred"}), 500
    

@stats.route("/average-work-time-per-day", methods=["GET"])
def average_work_time_per_day():
    try:
        time_differences = db.session.query(
            func.date(TrackedTime.start_time),
            func.sum(
                func.extract('epoch', TrackedTime.end_time) -
                func.extract('epoch', TrackedTime.start_time)
            ).label("daily_total")
        ).group_by(func.date(TrackedTime.start_time)).subquery()

        avg_day_work = db.session.query(
            func.avg(time_differences.c.daily_total)
        ).scalar()

        avg_day_work = (avg_day_work / 60) / 60 if avg_day_work else 0 

        return jsonify({"avg_day_work": avg_day_work}), 200
    except:
        traceback.print_exc()
        return jsonify({"error": "An error occurred"}), 500
    

@stats.route("/highest-score", methods=["GET"])
def highest_score():
    try:
        # Calculate daily total tracked time
        time_differences = db.session.query(
            func.date(TrackedTime.start_time).label("date"),
            func.sum(
                func.extract('epoch', TrackedTime.end_time) - 
                func.extract('epoch', TrackedTime.start_time)
            ).label("daily_total")
        ).group_by(func.date(TrackedTime.start_time)).subquery()

        # Get the highest total tracked time
        highest_score = db.session.query(
            func.max(time_differences.c.daily_total)
        ).scalar()

        # Convert seconds to hours
        highest_score = (highest_score / 60) / 60 if highest_score else 0  

        return jsonify({"highest_score": highest_score}), 200

    except:
        traceback.print_exc()
        return jsonify({"error": "An error occurred"}), 500
    

@stats.route("/save-work", methods=["POST"])
def save_work():
    try:
        data = request.json
        print(data)
        start_time = datetime.strptime(data.get("start_time"), "%Y-%m-%d %H:%M:%S")
        end_time = datetime.strptime(data.get("end_time"), "%Y-%m-%d %H:%M:%S")

        if end_time < start_time:
            return jsonify({"msg": "End time smaller that start time!"}), 400

        if db.session.query(TrackedTime).filter_by(start_time=start_time).first():
            return jsonify({"msg": "This start time already exists!"}), 400
        
        db.session.add(
            TrackedTime(
                start_time=start_time,
                end_time=end_time,
                type=data.get("type")
            )
        )
        db.session.commit()

        return jsonify({"msg": "Saved!"}), 201
    except:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"error": "An error occurred"}), 500