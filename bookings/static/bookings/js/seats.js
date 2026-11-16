
const seatContainer = document.getElementById("seat-sections");
const selectedCount = document.getElementById("selected-count");
const totalPrice = document.getElementById("total-price");
const continueButton = document.getElementById("continue-btn");
const timerElement = document.getElementById("timer");

const selectedSeats = new Set();
let availableSeats = [];
let currentBookingId = null;
let countdownInterval = null;

function getCSRFToken() {
    return document.querySelector(
        '#csrf-form input[name="csrfmiddlewaretoken"]'
    )?.value || "";
}

function updateSummary() {
    selectedCount.textContent = `${selectedSeats.size} Seats`;
    totalPrice.textContent = (
        selectedSeats.size * TICKET_PRICE
    ).toFixed(2);
    continueButton.disabled = selectedSeats.size === 0;
}

function renderSeats() {
    seatContainer.innerHTML = "";

    const row = document.createElement("div");
    row.className = "seat-row";

    availableSeats.forEach(seat => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "seat";
        button.textContent = seat.seat_number;

        if (seat.status !== "AVAILABLE") {
            button.classList.add(seat.status.toLowerCase());
            button.disabled = true;
            selectedSeats.delete(seat.id);
        } else if (selectedSeats.has(seat.id)) {
            button.classList.add("selected");
        }

        button.addEventListener("click", () => {
            if (selectedSeats.has(seat.id)) {
                selectedSeats.delete(seat.id);
            } else {
                selectedSeats.add(seat.id);
            }
            renderSeats();
        });

        row.appendChild(button);
    });

    seatContainer.appendChild(row);
    updateSummary();
}

async function loadSeats() {
    try {
        const response = await fetch(
            `/bookings/show/${SHOW_ID}/seats/`
        );
        if (!response.ok) throw new Error("Unable to load seats");

        const data = await response.json();
        availableSeats = data.seats;
        renderSeats();
    } catch (error) {
        console.error(error);
        seatContainer.textContent = "Unable to load seats.";
    }
}

function startTimer() {
    clearInterval(countdownInterval);
    let remaining = 120;

    countdownInterval = setInterval(() => {
        remaining--;
        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;

        timerElement.textContent =
            `${String(minutes).padStart(2, "0")}:` +
            `${String(seconds).padStart(2, "0")}`;

        if (remaining <= 0) {
            clearInterval(countdownInterval);
            alert("Reservation time expired. Please select seats again.");
            window.location.reload();
        }
    }, 1000);
}

async function verifyPayment(paymentResponse) {
    const response = await fetch("/payments/verify/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken()
        },
        body: JSON.stringify({
            booking_id: currentBookingId,
            razorpay_payment_id: paymentResponse.razorpay_payment_id,
            razorpay_order_id: paymentResponse.razorpay_order_id,
            razorpay_signature: paymentResponse.razorpay_signature
        })
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Payment verification failed");
    }

    window.location.href =
        `/payments/confirmation/${data.booking_id || currentBookingId}/`;
}

async function startPayment() {
    const response = await fetch(
        `/payments/create/${currentBookingId}/`,
        {
            method: "POST",
            headers: {
                "X-CSRFToken": getCSRFToken()
            }
        }
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Could not create payment");
    }

    if (typeof Razorpay === "undefined") {
        throw new Error("Razorpay checkout script is missing");
    }

    const checkout = new Razorpay({
        key: data.key_id || data.key,
        amount: data.amount,
        currency: data.currency || "INR",
        name: "Book My Show",
        description: "Movie Ticket Booking",
        order_id: data.order_id || data.razorpay_order_id,
        handler: async function (paymentResponse) {
            try {
                await verifyPayment(paymentResponse);
            } catch (error) {
                alert(error.message);
            }
        },
        theme: {
            color: "#f84464"
        }
    });

    checkout.open();
}

continueButton.addEventListener("click", async () => {
    if (selectedSeats.size === 0) return;

    continueButton.disabled = true;

    try {
        const response = await fetch(
            `/bookings/show/${SHOW_ID}/reserve/`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken()
                },
                body: JSON.stringify({
                    seat_ids: [...selectedSeats]
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Seat reservation failed");
        }

        currentBookingId = data.booking_id;
        startTimer();
        await startPayment();
    } catch (error) {
        alert(error.message);
        await loadSeats();
    } finally {
        if (!currentBookingId) {
            updateSummary();
        }
    }
});

loadSeats();
setInterval(loadSeats, 5000);
