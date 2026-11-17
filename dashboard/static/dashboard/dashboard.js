const query = window.location.search;
const money = value => "₹" + Number(value || 0).toLocaleString("en-IN", {maximumFractionDigits:2});
document.getElementById("summary-export").href = "/dashboard/export/" + query;
document.getElementById("booking-export").href = "/dashboard/export/" + (query ? query + "&" : "?") + "type=bookings";
function cards(id, values) {
    const target = document.getElementById(id);
    target.replaceChildren();
    for (const [label, value] of values) {
        const card = document.createElement("div");
        card.className = "card";
        card.textContent = label;
        const number = document.createElement("strong");
        number.textContent = value;
        card.append(number);
        target.append(card);
    }
}
function table(id, headers, rows) {
    const target = document.getElementById(id);
    target.replaceChildren();
    if (!rows.length) { target.textContent = "No records in this period."; return; }
    const table = document.createElement("table");
    const head = table.createTHead().insertRow();
    for (const title of headers) {
        const cell = document.createElement("th");
        cell.scope = "col"; cell.textContent = title; head.append(cell);
    }
    const body = table.createTBody();
    for (const values of rows) {
        const row = body.insertRow();
        values.forEach(value => { row.insertCell().textContent = value; });
    }
    target.append(table);
}
async function refreshDashboard() {
    try {
        const response = await fetch("/dashboard/data/" + query, {cache:"no-store"});
        if (!response.ok || response.redirected) throw new Error("Check your date range or sign in with dashboard permission.");
        const d = await response.json();
        document.getElementById("id_start").value = d.start;
        document.getElementById("id_end").value = d.end;
        cards("calendar", Object.entries(d.calendar_revenue).map(([key, value]) => [key[0].toUpperCase()+key.slice(1), money(value)]));
        cards("summary", [
            ["Revenue",money(d.totals.revenue)], ["Bookings",d.booking_totals.total],
            ["Confirmed",d.booking_totals.confirmed], ["Pending",d.booking_totals.pending],
            ["Cancelled",d.booking_totals.cancelled+" ("+d.booking_totals.cancellation_percent+"%)"],
            ["Refunded",money(d.totals.refunded)+" · "+d.totals.refund_count],
            ["Refund review",money(d.refunds_pending.amount)+" · "+d.refunds_pending.count],
            ["Failed orders",d.totals.failed], ["New users",d.new_users],
        ]);
        table("trends", [d.bucket,"Bookings","Confirmed","Cancelled"],d.trends.map(r=>[r.period.slice(0,10),r.total,r.confirmed,r.cancelled]));
        table("growth",[d.bucket,"New users"],d.growth.map(r=>[r.period.slice(0,10),r.total]));
        table("occupancy",["Theater","Shows","Capacity","Booked","Occupancy"],d.occupancy.map(r=>[r.screen__theater__name,r.shows,r.capacity,r.booked,r.percentage+"%"]));
        table("movies",["Movie","Bookings"],d.movies.map(r=>[r.show__movie__title,r.total]));
        table("theaters",["Theater","Revenue","Paid orders"],d.theaters.map(r=>[r.booking__show__screen__theater__name,money(r.revenue),r.transactions]));
        table("hours",["Hour (IST)","Bookings"],d.hours.map(r=>[String(r.hour).padStart(2,"0")+":00",r.total]));
        document.getElementById("status").textContent = "Updated "+new Date(d.generated).toLocaleTimeString()+" · Refreshes every 30 seconds";
    } catch(error) {
        document.getElementById("status").textContent = error.message;
    }
}
refreshDashboard();
setInterval(() => { if (!document.hidden) refreshDashboard(); },30000);
