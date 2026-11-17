const filterForm = document.getElementById("discovery-filters");
const results = document.getElementById("discovery-results");
const statusText = document.getElementById("filter-status");
let timer;
let controller;
async function updateResults(url) {
    controller?.abort();
    controller = new AbortController();
    const signal = controller.signal;
    statusText.textContent = "Updating movies…";
    const endpoint = new URL(url, location.href);
    endpoint.searchParams.set("partial","1");
    try {
        const response = await fetch(endpoint, {signal});
        if (!response.ok) throw new Error("Could not update movies. Try Apply filters again.");
        const html = await response.text();
        if (signal.aborted) return;
        results.innerHTML = html;
        endpoint.searchParams.delete("partial");
        history.replaceState(null,"",endpoint.pathname+"?"+endpoint.searchParams.toString());
        statusText.textContent = "";
    } catch (error) {
        if (error.name !== "AbortError") statusText.textContent = error.message;
    }
}
function applyFilters() {
    clearTimeout(timer);
    const params = new URLSearchParams(new FormData(filterForm));
    for (const [key,value] of [...params]) if (!value) params.delete(key);
    updateResults("?"+params.toString());
}
filterForm.addEventListener("submit",event => { event.preventDefault(); applyFilters(); });
filterForm.addEventListener("change",applyFilters);
filterForm.addEventListener("input",() => {
    controller?.abort();
    clearTimeout(timer);
    timer = setTimeout(applyFilters,350);
});
results.addEventListener("click",event => {
    const link = event.target.closest(".pagination a");
    if (link) { event.preventDefault(); updateResults(link.href); }
});
