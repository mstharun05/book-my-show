
const seatContainer = document.getElementById("seat-sections");
const selectedCount = document.getElementById("selected-count");
const totalPrice = document.getElementById("total-price");
const continueBtn = document.getElementById("continue-btn");
const timerDisplay = document.getElementById("timer");

const selectedSeats = new Set();

let seatPrice = TICKET_PRICE;
let timerSeconds = 120;
let reservationActive = false;
let currentBookingId = null;
let paymentInProgress = false;
let bookingConfirmed = false;
let timerInterval = null;
let availabilityInterval = null;
let paymentOrder = null;

const availabilityURL = `/bookings/show/${SHOW_ID}/seats/`;
const reserveURL = `/bookings/show/${SHOW_ID}/reserve/`;

function getCSRFToken() {
    return document.querySelector(
        '#csrf-form input[name="csrfmiddlewaretoken"]'
    )?.value;
}

function updateSummary() {
    selectedCount.textContent = `${selectedSeats.size} Seats`;

    totalPrice.textContent = (
        selectedSeats.size * seatPrice
    ).toFixed(2);

    if (bookingConfirmed) {
        continueBtn.textContent = "Booking Confirmed";
        continueBtn.disabled = true;
    } else if (reservationActive) {
        continueBtn.textContent = "Pay Now";
        continueBtn.disabled = paymentInProgress;
    } else {
        continueBtn.textContent = "Continue";
        continueBtn.disabled = selectedSeats.size === 0;
    }
}

function createSeatButton(seat) {
    const button = document.createElement("button");

    button.type = "button";
    button.className = "seat";
    button.textContent = seat.seat_number;
    button.dataset.id = seat.id;

    const status = seat.status.toLowerCase();

    if (status === "booked" || status === "reserved") {
        button.classList.add(status);
        button.disabled = true;
    } else if (selectedSeats.has(String(seat.id))) {
        button.classList.add("selected");
    }

    button.addEventListener("click", () => {
        if (reservationActive || bookingConfirmed || button.disabled) {
            return;
        }

        const id = String(seat.id);

        if (selectedSeats.has(id)) {
            selectedSeats.delete(id);
            button.classList.remove("selected");
        } else {
            selectedSeats.add(id);
            button.classList.add("selected");
        }

        updateSummary();
    });

    return button;
}

function renderSeats(seats) {
    seatContainer.innerHTML = "";

    const rows = {};

    seats.forEach(seat => {
        const match = seat.seat_number.match(/^([A-Za-z]+)/);
        const rowName = match ? match[1] : "SEATS";

        if (!rows[rowName]) {
            rows[rowName] = [];
        }

        rows[rowName].push(seat);
    });

    Object.entries(rows).forEach(([rowName, rowSeats]) => {
        const rowDiv = document.createElement("div");
        rowDiv.className = "seat-row";

        const label = document.createElement("span");
        label.className = "row-label";
        label.textContent = rowName;

        rowDiv.appendChild(label);

        rowSeats.forEach(seat => {
            rowDiv.appendChild(createSeatButton(seat));
        });

        seatContainer.appendChild(rowDiv);
    });
}

async function loadSeats() {
    try {
        const response = await fetch(availabilityURL);

        if (!response.ok) {
            throw new Error("Unable to load seat availability.");
        }

        const data = await response.json();

        seatPrice = Number(data.ticket_price);

        renderSeats(data.seats);
        updateSummary();

    } catch (error) {
        console.error(error);
        alert("Could not load seats. Please refresh the page.");
    }
}

function startTimer() {
    timerSeconds = 120;

    clearInterval(timerInterval);

    timerInterval = setInterval(() => {
        timerSeconds--;

        const minutes = String(
            Math.floor(timerSeconds / 60)
        ).padStart(2, "0");

        const seconds = String(
            timerSeconds % 60
        ).padStart(2, "0");

        timerDisplay.textContent = `${minutes}:${seconds}`;

        if (timerSeconds <= 0) {
            clearInterval(timerInterval);

            reservationActive = false;
            currentBookingId = null;
            selectedSeats.clear();

            timerDisplay.textContent = "Expired";

            if (!bookingConfirmed) {
                alert(
                    "Your reservation has expired. Please select seats again."
                );
            }

            loadSeats();
            updateSummary();
        }

    }, 1000);
}

async function createPaymentOrder() {
    const response = await fetch(
        `/payments/create/${currentBookingId}/`,
        {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": getCSRFToken()
            }
        }
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data.error || "Could not create payment order."
        );
    }

    return data;
}

/* VERIFY RAZORPAY PAYMENT */
async function verifyPayment(response) {
    const result = await fetch("/payments/verify/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken()
        },
        body: JSON.stringify({
            payment_id: paymentOrder.payment_id,
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature
        })
    });

    const data = await result.json();

    if (!result.ok) {
        throw new Error(
            data.error || "Payment verification failed."
        );
    }

    bookingConfirmed = true;
    paymentInProgress = false;

    clearInterval(timerInterval);
    clearInterval(availabilityInterval);

    timerDisplay.textContent = "Completed";

    // Redirect to booking confirmation page.
    window.location.href =
        `/payments/confirmation/${data.booking_id}/`;
}

/* OPEN RAZORPAY CHECKOUT */
async function startPayment() {
    if (paymentInProgress || !currentBookingId) {
        return;
    }

    if (typeof Razorpay === "undefined") {
        alert("Razorpay Checkout did not load. Please refresh the page.");
        return;
    }

    paymentInProgress = true;
    updateSummary();

    try {
        paymentOrder = await createPaymentOrder();

        const options = {
            key: paymentOrder.key,
            amount: paymentOrder.amount,
            currency: paymentOrder.currency,
            name: "Book My Show",
            description: "Movie Ticket Booking",
            order_id: paymentOrder.order_id,

            handler: async function (response) {
                try {
                    await verifyPayment(response);
                } catch (error) {
                    paymentInProgress = false;
                    updateSummary();
                    alert(error.message);
                }
            },

            modal: {
                ondismiss: function () {
                    paymentInProgress = false;
                    updateSummary();
                }
            },

            theme: {
                color: "#f84464"
            }
        };

        const checkout = new Razorpay(options);

        checkout.on("payment.failed", function (response) {
            paymentInProgress = false;
            updateSummary();

            alert(
                response.error.description ||
                "Payment failed. You can try again before the timer expires."
            );
        });

        checkout.open();

    } catch (error) {
        paymentInProgress = false;
        updateSummary();
        alert(error.message);
    }
}

/* RESERVE SELECTED SEATS */
continueBtn.addEventListener("click", async () => {
    if (bookingConfirmed || paymentInProgress) {
        return;
    }

    if (reservationActive && currentBookingId) {
        startPayment();
        return;
    }

    if (selectedSeats.size === 0) {
        return;
    }

    continueBtn.disabled = true;
    continueBtn.textContent = "Reserving...";

    try {
        const response = await fetch(reserveURL, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken()
            },
            body: JSON.stringify({
                seat_ids: Array.from(selectedSeats).map(Number)
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Seat reservation failed."
            );
        }

        currentBookingId = data.booking_id;
        reservationActive = true;

        document.querySelectorAll(".seat.selected").forEach(seat => {
            seat.classList.remove("selected");
            seat.classList.add("reserved");
            seat.disabled = true;
        });

        startTimer();
        updateSummary();

        // Automatically open Razorpay after reservation.
        startPayment();

    } catch (error) {
        alert(error.message);

        await loadSeats();

        continueBtn.textContent = "Continue";
        continueBtn.disabled = selectedSeats.size === 0;
    }
});

/* INITIALIZE SEAT PAGE */
loadSeats();

availabilityInterval = setInterval(() => {
    if (!reservationActive && !bookingConfirmed) {
        loadSeats();
    }
}, 5000);
