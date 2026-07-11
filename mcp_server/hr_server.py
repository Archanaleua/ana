from dotenv import load_dotenv
load_dotenv()

from mcp.server.fastmcp import FastMCP
from services.supabase_client import get_supabase_admin

mcp = FastMCP("ANA HR Assistant")


@mcp.tool()
def find_employee(name: str, city: str = None, department: str = None) -> dict:
    """
    Find employee(s) matching a name. If the caller already knows a distinguishing
    detail (city and/or department — e.g. from earlier in the conversation, or
    because the user provided it upfront), pass it here to filter server-side and
    resolve ambiguity deterministically, instead of guessing from raw matches.
    If multiple employees still match after filtering, returns all of them with
    employee_id, city, and department so the caller can ask the user to clarify.
    """
    sb = get_supabase_admin()
    query = sb.table("employees_v2").select(
        "employee_id,name,department,designation,city"
    ).ilike("name", f"%{name}%")

    if city:
        query = query.ilike("city", f"%{city}%")
    if department:
        query = query.ilike("department", f"%{department}%")

    rows = query.execute()
    matches = rows.data or []

    if not matches:
        return {"error": "No employee found matching that name/city/department combination"}
    if len(matches) == 1:
        return {"match_count": 1, "employee": matches[0]}
    return {
        "match_count": len(matches),
        "message": "Multiple employees found with this name. Ask the user to clarify by city or department.",
        "matches": matches,
    }


@mcp.tool()
def get_employee(employee_id: str) -> dict:
    """Get an employee's basic details by their unique employee_id (e.g. 'EMP001')."""
    sb = get_supabase_admin()
    row = (
        sb.table("employees_v2")
        .select("employee_id,name,department,designation,city,salary,date_of_joining,manager_name")
        .eq("employee_id", employee_id)
        .single()
        .execute()
    )
    return row.data or {"error": "Employee not found"}


@mcp.tool()
def list_employees() -> list[dict]:
    """List all employees with their basic details."""
    sb = get_supabase_admin()
    rows = (
        sb.table("employees_v2")
        .select("employee_id,name,department,designation,city")
        .execute()
    )
    return rows.data or []


@mcp.tool()
def get_attendance_on_date(employee_id: str, date: str) -> dict:
    """Check if an employee was present, absent, or on leave on a specific date (format: YYYY-MM-DD)."""
    sb = get_supabase_admin()
    row = (
        sb.table("attendance_v2")
        .select("date,status")
        .eq("employee_id", employee_id)
        .eq("date", date)
        .execute()
    )
    if not row.data:
        return {"error": "No record found for that date"}
    return row.data[0]


@mcp.tool()
def get_leave_count_in_range(employee_id: str, start_date: str, end_date: str) -> dict:
    """Count how many leaves an employee took between two dates (format: YYYY-MM-DD)."""
    sb = get_supabase_admin()
    rows = (
        sb.table("attendance_v2")
        .select("date,status")
        .eq("employee_id", employee_id)
        .gte("date", start_date)
        .lte("date", end_date)
        .eq("status", "leave")
        .execute()
    )
    return {
        "employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "leaves_taken": len(rows.data or []),
    }


@mcp.tool()
def get_attendance_summary(employee_id: str, start_date: str, end_date: str) -> dict:
    """Get a full attendance summary (present/absent/leave counts) for an employee over a date range (format: YYYY-MM-DD)."""
    sb = get_supabase_admin()
    rows = (
        sb.table("attendance_v2")
        .select("status")
        .eq("employee_id", employee_id)
        .gte("date", start_date)
        .lte("date", end_date)
        .execute()
    )
    records = rows.data or []
    present = sum(1 for r in records if r["status"] == "present")
    absent = sum(1 for r in records if r["status"] == "absent")
    leave = sum(1 for r in records if r["status"] == "leave")
    return {
        "employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "present": present,
        "absent": absent,
        "leave": leave,
    }


@mcp.tool()
def get_absentees_on_date(date: str) -> list[dict]:
    """Get a list of all employees who were absent on a specific date (format: YYYY-MM-DD)."""
    sb = get_supabase_admin()
    rows = (
        sb.table("attendance_v2")
        .select("employee_id,date,status")
        .eq("date", date)
        .eq("status", "absent")
        .execute()
    )
    absent_ids = [r["employee_id"] for r in (rows.data or [])]
    if not absent_ids:
        return []
    emp_rows = (
        sb.table("employees_v2")
        .select("employee_id,name,department,city")
        .in_("employee_id", absent_ids)
        .execute()
    )
    return emp_rows.data or []


@mcp.tool()
def get_employees_on_leave_in_range(start_date: str, end_date: str) -> list[dict]:
    """Get a list of all employees who took leave at any point between two dates (format: YYYY-MM-DD)."""
    sb = get_supabase_admin()
    rows = (
        sb.table("attendance_v2")
        .select("employee_id,date,status")
        .gte("date", start_date)
        .lte("date", end_date)
        .eq("status", "leave")
        .execute()
    )
    leave_records = rows.data or []
    if not leave_records:
        return []

    # Count leave days per employee
    leave_counts: dict[str, int] = {}
    for r in leave_records:
        leave_counts[r["employee_id"]] = leave_counts.get(r["employee_id"], 0) + 1

    emp_ids = list(leave_counts.keys())
    emp_rows = (
        sb.table("employees_v2")
        .select("employee_id,name,department,city")
        .in_("employee_id", emp_ids)
        .execute()
    )
    employees = emp_rows.data or []
    for e in employees:
        e["leave_days_in_range"] = leave_counts.get(e["employee_id"], 0)
    return employees


@mcp.tool()
def get_leave_balance(employee_id: str, annual_quota: int = 24) -> dict:
    """
    Get an employee's remaining leave balance for the current calendar year.
    Assumes a default annual quota of 24 leaves unless specified.
    """
    sb = get_supabase_admin()
    from datetime import date as date_cls

    year_start = f"{date_cls.today().year}-01-01"
    year_end = f"{date_cls.today().year}-12-31"

    rows = (
        sb.table("attendance_v2")
        .select("date,status")
        .eq("employee_id", employee_id)
        .gte("date", year_start)
        .lte("date", year_end)
        .eq("status", "leave")
        .execute()
    )
    taken = len(rows.data or [])
    return {
        "employee_id": employee_id,
        "year": date_cls.today().year,
        "annual_quota": annual_quota,
        "leaves_taken": taken,
        "leaves_remaining": annual_quota - taken,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")