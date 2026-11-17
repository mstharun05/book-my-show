const container = document.getElementById("seat-sections");
const action = document.getElementById("continue-btn");
const timer = document.getElementById("timer");
const message = document.createElement("p");
message.setAttribute("role", "status");
container.before(message);
const selected = new Set();
let bookingId = null;
let expiresAt = 0;
let busy = false;
let dirty = false;
let seats = [];
const csrf = document.querySelector('[name="csrfmiddlewaretoken"]').value;

async function api(url, body) {
    const options = {cache: "no-store"};
    if (body !== undefined) {
        Object.assign(options, {
            method: "POST",
            headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
            body: JSON.stringify(body),
        });
    }
    const response = await fetch(url, options);
    if (response.redirected) throw new Error("Please sign in again.");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed. Please try again.");
    return data;
}

function render() {
    container.replaceChildren();
    const row = document.createElement("div");
    row.className = "seat-row";
    row.style.flexWrap = "wrap";
    seats.forEach(seat => {
        const button = document.createElement("button");
        button.type = "button";
        const chosen = selected.has(seat.id);
        button.className = "seat " + (chosen ? "selected" : seat.status.toLowerCase());
        button.textContent = seat.seat_number;
        button.disabled = busy || (seat.status !== "AVAILABLE" && !seat.owned);
        button.setAttribute("aria-pressed", String(chosen));
        button.setAttribute("aria-label", "Seat " + seat.seat_number + ", " + (seat.owned ? "reserved by you" : seat.status));
        button.onclick = () => {
            if (chosen) selected.delete(seat.id);
            else selected.add(seat.id);
            dirty = true;
            render();
        };
        row.append(button);
    });
    container.append(row);
    document.getElementById("selected-count").textContent = selected.size + " Seats";
    document.getElementById("total-price").textContent = (selected.size * TICKET_PRICE).toFixed(2);
    action.textContent = bookingId ? (dirty ? "Update reservation" : "Pay Now") : "Reserve seats";
    action.disabled = busy || (!selected.size && !bookingId);
}

async function refresh() {
    if (busy) return;
    try {
        const data = await api('/bookings/show/' + SHOW_ID + '/seats/');
        if (busy) return;
        seats = data.seats;
        const owned = seats.filter(seat => seat.owned);
        const hold = owned.find(seat => seat.booking_id === bookingId) || owned[0];
        if (hold) {
            bookingId = hold.booking_id;
            expiresAt = Date.now() + (new Date(hold.reserved_until).getTime() - new Date(data.server_time).getTime());
            if (!dirty) {
                selected.clear();
                owned.filter(seat => seat.booking_id === bookingId).forEach(seat => selected.add(seat.id));
            }
        } else if (bookingId) {
            bookingId = null;
            expiresAt = 0;
            dirty = false;
            selected.clear();
            message.textContent = "Reservation expired. Select seats again.";
        }
        for (const id of selected) {
            if (!seats.some(seat => seat.id === id && (seat.status === "AVAILABLE" || seat.owned))) {
                selected.delete(id);
            }
        }
        render();
    } catch (error) {
        message.textContent = error.message;
    }
}

async function pay() {
    const id = bookingId;
    const order = await api('/payments/create/' + id + '/', {});
    if (typeof Razorpay === "undefined") throw new Error("Payment checkout could not load.");
    let completed = false;
    async function finishCheckout(url, body, notice) {
        try {
            const result = await api(url, body);
            if (result.status === "SUCCESS" || result.status === "CONFIRMED") {
                completed = true;
                window.location.href = '/payments/confirmation/' + id + '/';
                return;
            }
            message.textContent = notice;
        } catch (error) {
            message.textContent = error.message;
        } finally {
            busy = false;
            await refresh();
        }
    }
    const checkout = new Razorpay({
        key: order.key_id, amount: order.amount, currency: order.currency,
        order_id: order.order_id, name: "Book My Show",
        retry: {enabled: false},
        handler: async response => {
            completed = true;
            try {
                await api('/payments/verify/', {...response, booking_id: id});
                window.location.href = '/payments/confirmation/' + id + '/';
            } catch (error) {
                message.textContent = error.message;
                busy = false;
                await refresh();
            }
        },
        modal: {ondismiss: async () => {
            if (!completed) {
                await finishCheckout('/payments/cancel/' + id + '/', {}, "Payment cancelled. Select seats to retry.");
            }
        }},
    });
    checkout.on("payment.failed", async response => {
        completed = true;
        const paymentId = response.error.metadata?.payment_id;
        if (paymentId) {
            await finishCheckout('/payments/failed/' + id + '/', {payment_id: paymentId}, "Payment failed. Select seats to retry.");
        } else {
            await finishCheckout('/payments/cancel/' + id + '/', {}, "Checkout failed. Select seats to retry.");
        }
        checkout.close();
    });
    checkout.open();
}

action.onclick = async () => {
    if (busy) return;
    busy = true;
    render();
    try {
        if (bookingId && !dirty) {
            await pay();
            return;
        }
        const data = await api('/bookings/show/' + SHOW_ID + '/reserve/', {
            seat_ids: [...selected], booking_id: bookingId,
        });
        bookingId = data.booking_id;
        expiresAt = data.reserved_until ? Date.now() + (new Date(data.reserved_until).getTime() - new Date(data.server_time).getTime()) : 0;
        dirty = false;
        message.textContent = bookingId ? "Seats reserved. You can change seats before paying. Changes keep the original expiry." : "Reservation released.";
    } catch (error) {
        message.textContent = error.message;
    }
    busy = false;
    await refresh();
};
setInterval(() => {
    if (!expiresAt) { timer.textContent = "No active reservation"; return; }
    const seconds = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
    timer.textContent = Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
}, 250);
refresh();
setInterval(refresh, 2000);
