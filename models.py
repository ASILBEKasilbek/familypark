# models.py
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    first_name = Column(String(100))
    username = Column(String(100))
    phone = Column(String(20), nullable=False)
    source = Column(String(100), nullable=False)
    profile_photo = Column(Text)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    attended = Column(Boolean, default=False)
    attended_date = Column(DateTime(timezone=True), nullable=True)


class Admin(Base):
    __tablename__ = "admins"

    telegram_id = Column(BigInteger, primary_key=True)
    role = Column(String(20), nullable=False, default="cashier")
    full_name = Column(String(100), nullable=True)
    added_by = Column(BigInteger, nullable=True)
    place = Column(String(100), nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)


class QRLog(Base):
    __tablename__ = "qr_logs"

    id = Column(BigInteger, primary_key=True)
    admin_id = Column(BigInteger)
    source_key = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, nullable=False)  
    place = Column(String(50), nullable=False)    
    marked_by = Column(BigInteger, nullable=False) 
    marked_at = Column(DateTime(timezone=True), server_default=func.now())