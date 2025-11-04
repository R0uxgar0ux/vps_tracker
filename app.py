import os
from datetime import datetime
import requests

from flask import Flask, request, redirect, url_for, render_template
from sqlalchemy import create_engine, Column, Integer, String, Date, Float, text
from sqlalchemy.orm import sessionmaker, declarative_base
from jinja2 import DictLoader

# ----- paths / db -----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "vps.db")
DB_URL = f"sqlite:///{DB_PATH}"

app = Flask(__name__)

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()


class VPS(Base):
    __tablename__ = "vps"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    provider = Column(String, nullable=True)
    provider_domain = Column(String, nullable=True)
    ip = Column(String, nullable=True)
    location = Column(String, nullable=True)
    renewal_date = Column(Date, nullable=True)
    monthly_cost = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    notes = Column(String, nullable=True)


# создаём таблицу если её нет
Base.metadata.create_all(engine)

# добавим колонку location если нет
with engine.connect() as conn:
    res = conn.execute(text("PRAGMA table_info(vps);")).fetchall()
    cols = [r[1] for r in res]
    if "location" not in cols:
        conn.execute(text("ALTER TABLE vps ADD COLUMN location TEXT;"))


# ---------- helpers ----------

def clean_str(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.strip() or None


def geolocate_ip(ip: str | None) -> str | None:
    """
    Возвращаем строку в формате:
    RU Russia, Moscow
    (то есть первые 2 буквы — ISO-код страны, дальше — человекочитаемо)
    В шаблоне по этим 2 буквам нарисуем флажок.
    """
    if not ip:
        return None

    def norm_code(code: str | None) -> str | None:
        if not code:
            return None
        code = code.strip().upper()
        if len(code) != 2:
            return None
        return code

    # 1) ipapi.co
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=3)
        if r.status_code == 200:
            data = r.json()
            if not data.get("error"):
                country = data.get("country_name") or data.get("country")
                city = data.get("city")
                code = norm_code(data.get("country_code"))
                if country:
                    parts = []
                    if code:
                        parts.append(code)
                    parts.append(country)
                    loc = " ".join(parts)
                    if city:
                        loc += f", {city}"
                    return loc
    except Exception:
        pass

    # 2) ipwho.is
    try:
        r = requests.get(f"https://ipwho.is/{ip}", timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data.get("success", True):
                country = data.get("country")
                city = data.get("city")
                code = norm_code(data.get("country_code"))
                if country:
                    parts = []
                    if code:
                        parts.append(code)
                    parts.append(country)
                    loc = " ".join(parts)
                    if city:
                        loc += f", {city}"
                    return loc
    except Exception:
        pass

    return None


def loc_has_iso_prefix(loc: str | None) -> bool:
    """
    Проверяем, начинается ли локация с двух латинских букв и пробела, типа 'RU ...'
    """
    if not loc or len(loc) < 3:
        return False
    if not loc[0:2].isalpha():
        return False
    if loc[2] != " ":
        return False
    return True


# ---------- templates ----------

BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>VPS Tracker</title>
  <link rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  <style>
    body { padding-top: 30px; }
    .expired { background: #f8d7da !important; }
    .soon { background: #fff3cd !important; }
    .favico { width: 16px; height: 16px; margin-right: 4px; vertical-align: text-bottom; }
    .flag { width: 18px; height: 13px; margin-right: 5px; border: 1px solid #ddd; }
  </style>
</head>
<body>
<div class="container">
  <h1 class="mb-4">VPS Tracker</h1>
  {% block content %}{% endblock %}
  <hr>
  <p class="text-muted">Self-hosted VPS tracker</p>
</div>
</body>
</html>
"""

LIST_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
  <div class="mb-3 d-flex justify-content-between align-items-start">
    <a href="{{ url_for('add_vps') }}" class="btn btn-primary">+ Add VPS</a>
    <div class="fw-bold text-end">
      Total per month:<br>
      {% if totals %}
        {% for cur, amount in totals.items() %}
          {{ cur }} {{ "%.2f"|format(amount) }}<br>
        {% endfor %}
      {% else %}
        0
      {% endif %}
    </div>
  </div>
  <table class="table table-bordered table-striped align-middle">
    <thead>
      <tr>
        <th>ID</th>
        <th>Name / Provider</th>
        <th>IP</th>
        <th>Location</th>
        <th>Renewal date</th>
        <th>Monthly cost</th>
        <th>Notes</th>
        <th style="width:140px"></th>
      </tr>
    </thead>
    <tbody>
    {% for v in vps_list %}
      {% set row_class = "" %}
      {% if v.renewal_date %}
        {% if v.renewal_date < today %}
          {% set row_class = "expired" %}
        {% elif (v.renewal_date - today).days <= 7 %}
          {% set row_class = "soon" %}
        {% endif %}
      {% endif %}
      <tr class="{{ row_class }}">
        <td>{{ v.id }}</td>
        <td>
            {% set icon = None %}
            {% if v.provider_domain %}
              {% set d = v.provider_domain %}
              {% if d.endswith('.ico') or d.endswith('.png') or d.endswith('.jpg') or d.endswith('.jpeg') or d.endswith('.svg') %}
                {% set icon = d %}
              {% elif d.startswith('http://') or d.startswith('https://') %}
                {% set rest = d.split('://', 1)[1] %}
                {% if '/' in rest %}
                  {% set icon = d.rstrip('/') ~ '/favicon.ico' %}
                {% else %}
                  {% set icon = 'https://www.google.com/s2/favicons?domain=' ~ rest %}
                {% endif %}
              {% else %}
                {% set icon = 'https://www.google.com/s2/favicons?domain=' ~ d %}
              {% endif %}
            {% endif %}
            {% if icon %}
              <img class="favico" src="{{ icon }}" alt="">
            {% endif %}
            <strong>{{ v.name }}</strong><br>
            <small>{{ v.provider or "" }}</small>
        </td>
        <td>{{ v.ip or "" }}</td>
        <td>
          {% if v.location and v.location|length >= 3 and v.location[0:2].isalpha() and v.location[2] == ' ' %}
            {% set cc = v.location[0:2] %}
            {% set rest = v.location[3:] %}
            <img class="flag" src="https://flagcdn.com/16x12/{{ cc|lower }}.png" alt="{{ cc }}">
            {{ rest }}
          {% else %}
            {{ v.location or "" }}
          {% endif %}
        </td>
        <td>{{ v.renewal_date.strftime("%Y-%m-%d") if v.renewal_date else "" }}</td>
        <td>
          {% if v.monthly_cost %}
            {{ "%.2f"|format(v.monthly_cost) }} {{ v.currency or "" }}
          {% endif %}
        </td>
        <td>{{ v.notes or "" }}</td>
        <td>
          <a href="{{ url_for('edit_vps', vps_id=v.id) }}" class="btn btn-sm btn-secondary">Edit</a>
          <a href="{{ url_for('delete_vps', vps_id=v.id) }}" class="btn btn-sm btn-danger"
             onclick="return confirm('Delete?');">Del</a>
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
{% endblock %}
"""

FORM_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
  <form method="post" class="row g-3">
    <div class="col-md-6">
      <label class="form-label">Name*</label>
      <input type="text" name="name" required class="form-control" value="{{ vps.name if vps else '' }}">
    </div>
    <div class="col-md-6">
      <label class="form-label">Provider</label>
      <input type="text" name="provider" class="form-control" value="{{ vps.provider if vps else '' }}">
    </div>
    <div class="col-md-6">
      <label class="form-label">Provider domain / icon URL</label>
      <input type="text" name="provider_domain" class="form-control"
             placeholder="contabo.com или https://site.com/..."
             value="{{ vps.provider_domain if vps else '' }}">
    </div>
    <div class="col-md-4">
      <label class="form-label">Public IP</label>
      <input type="text" name="ip" class="form-control" value="{{ vps.ip if vps else '' }}">
    </div>
    <div class="col-md-4">
      <label class="form-label">Renewal date</label>
      <input type="date" name="renewal_date" class="form-control"
             value="{{ vps.renewal_date.strftime('%Y-%m-%d') if vps and vps.renewal_date else '' }}">
    </div>
    <div class="col-md-2">
      <label class="form-label">Monthly cost</label>
      <input type="number" step="0.01" name="monthly_cost" class="form-control"
             value="{{ vps.monthly_cost if vps and vps.monthly_cost else '' }}">
    </div>
    <div class="col-md-2">
      <label class="form-label">Currency</label>
      <input type="text" name="currency" class="form-control" value="{{ vps.currency if vps else 'EUR' }}">
    </div>
    <div class="col-12">
      <label class="form-label">Notes</label>
      <textarea name="notes" class="form-control" rows="3">{{ vps.notes if vps else '' }}</textarea>
    </div>
    <div class="col-12">
      <button class="btn btn-success" type="submit">Save</button>
      <a href="{{ url_for('list_vps') }}" class="btn btn-secondary">Cancel</a>
    </div>
  </form>
{% endblock %}
"""

app.jinja_loader = DictLoader({
    "base.html": BASE_TEMPLATE,
    "list.html": LIST_TEMPLATE,
    "form.html": FORM_TEMPLATE,
})


# ---------- routes ----------

@app.route("/")
def list_vps():
    # автообновление локаций: если пусто или не начинается с 2 букв + пробел
    vps_all = session.query(VPS).filter(VPS.ip.isnot(None)).all()
    changed = False
    for v in vps_all:
        if not v.location or not loc_has_iso_prefix(v.location):
            loc = geolocate_ip(v.ip)
            if loc and v.location != loc:
                v.location = loc
                changed = True
    if changed:
        session.commit()

    vps_list = session.query(VPS).order_by(VPS.renewal_date.is_(None), VPS.renewal_date).all()
    today = datetime.utcnow().date()

    # считаем тоталы по валютам
    totals = {}
    for v in vps_list:
        if not v.monthly_cost:
            continue
        cur = v.currency or ""
        totals[cur] = totals.get(cur, 0) + v.monthly_cost

    return render_template("list.html", vps_list=vps_list, today=today, totals=totals)


@app.route("/add", methods=["GET", "POST"])
def add_vps():
    if request.method == "POST":
        renewal_date = request.form.get("renewal_date") or None
        rd = datetime.strptime(renewal_date, "%Y-%m-%d").date() if renewal_date else None
        ip = clean_str(request.form.get("ip"))
        loc = geolocate_ip(ip) if ip else None

        v = VPS(
            name=request.form["name"],
            provider=request.form.get("provider"),
            provider_domain=clean_str(request.form.get("provider_domain")),
            ip=ip,
            location=loc,
            renewal_date=rd,
            monthly_cost=float(request.form["monthly_cost"]) if request.form.get("monthly_cost") else None,
            currency=request.form.get("currency"),
            notes=request.form.get("notes"),
        )
        session.add(v)
        session.commit()
        return redirect(url_for("list_vps"))
    return render_template("form.html", vps=None)


@app.route("/edit/<int:vps_id>", methods=["GET", "POST"])
def edit_vps(vps_id):
    vps = session.query(VPS).get(vps_id)
    if not vps:
        return "Not found", 404
    if request.method == "POST":
        vps.name = request.form["name"]
        vps.provider = request.form.get("provider")
        vps.provider_domain = clean_str(request.form.get("provider_domain"))
        new_ip = clean_str(request.form.get("ip"))
        vps.ip = new_ip

        # всегда обновляем локацию, если есть IP
        if new_ip:
            loc = geolocate_ip(new_ip)
            if loc:
                vps.location = loc
        else:
            vps.location = None

        renewal_date = request.form.get("renewal_date") or None
        vps.renewal_date = datetime.strptime(renewal_date, "%Y-%m-%d").date() if renewal_date else None
        vps.monthly_cost = float(request.form["monthly_cost"]) if request.form.get("monthly_cost") else None
        vps.currency = request.form.get("currency")
        vps.notes = request.form.get("notes")
        session.commit()
        return redirect(url_for("list_vps"))
    return render_template("form.html", vps=vps)


@app.route("/delete/<int:vps_id>")
def delete_vps(vps_id):
    vps = session.query(VPS).get(vps_id)
    if vps:
        session.delete(vps)
        session.commit()
    return redirect(url_for("list_vps"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
