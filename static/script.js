// App configuration
const STATIC_FLAVORS_URL = 'data/flavors.json';

// DOM elements
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const errorMessageEl = document.getElementById('errorMessage');
const flavorsGridEl = document.getElementById('flavorsGrid');
const currentDateEl = document.getElementById('currentDate');

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    loadFlavors();
});

// Set current date in header
function setCurrentDateToLocal() {
    // Use US Central time for consistency with backend
    const now = new Date();
    // Convert to US Central time string (YYYY-MM-DD)
    const centralOffset = -5 * 60; // UTC-5 for CDT, UTC-6 for CST (not handling DST here)
    const local = new Date(now.getTime() + (now.getTimezoneOffset() + centralOffset) * 60000);
    const yyyy = local.getFullYear();
    const mm = String(local.getMonth() + 1).padStart(2, '0');
    const dd = String(local.getDate()).padStart(2, '0');
    currentDateEl.textContent = `${yyyy}-${mm}-${dd}`;
}

// Load flavors from static JSON
async function loadFlavors() {
    showLoading();
    
    try {
        const flavors = await fetchFlavorsFromStatic();
        
        if (!flavors || flavors.length === 0) {
            showError('No flavors found for today. Please try again later.');
            return;
        }
        
        // Set the header date to the local date (US Central)
        setCurrentDateToLocal();
        
        displayFlavors(flavors);
        
    } catch (error) {
        console.error('Error loading flavors:', error);
        showError(`Failed to load flavors: ${error.message}`);
    }
}

// Fetch from static JSON file
async function fetchFlavorsFromStatic() {
    const response = await fetch(STATIC_FLAVORS_URL);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    if (data.flavors && Array.isArray(data.flavors)) {
        console.log(`Loaded ${data.flavors.length} flavors from static JSON (generated: ${data.generated_at})`);
        return data.flavors;
    }
    throw new Error('Invalid response format - expected flavors array');
}

// Show loading state
function showLoading() {
    loadingEl.style.display = 'block';
    errorEl.style.display = 'none';
    flavorsGridEl.innerHTML = '';
}

// Show error state
function showError(message) {
    loadingEl.style.display = 'none';
    errorEl.style.display = 'block';
    errorMessageEl.textContent = message;
    flavorsGridEl.innerHTML = '';
}

// Display flavors in the grid
function displayFlavors(flavors) {
    loadingEl.style.display = 'none';
    errorEl.style.display = 'none';
    
    // Clear existing content
    flavorsGridEl.innerHTML = '';
    
    // Create cards for each flavor
    flavors.forEach(flavor => {
        const card = createFlavorCard(flavor);
        flavorsGridEl.appendChild(card);
    });
}

// Create a flavor card element
function createFlavorCard(flavor) {
    const card = document.createElement('div');
    card.className = 'flavor-card';

    // Format description
    const description = flavor.description && flavor.description.trim() && 
                       flavor.description !== 'No description available' 
                       ? flavor.description 
                       : null;

    // Format date
    const date = formatDate(flavor.date);

    // Make the card clickable if a URL is present
    if (flavor.url) {
        card.classList.add('flavor-card-link');
        card.tabIndex = 0;
        card.setAttribute('role', 'link');
        card.setAttribute('aria-label', `Go to ${flavor.location} website`);
        card.addEventListener('click', (e) => {
            window.open(flavor.url, '_blank');
        });
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                window.open(flavor.url, '_blank');
            }
        });
    }

    card.innerHTML = `
        <div class="shop-header">
            <div class="shop-icon">
                <i class="fas fa-ice-cream"></i>
            </div>
            <div class="shop-name">${escapeHtml(flavor.location)}</div>
        </div>
        <div class="flavor-name">${escapeHtml(flavor.flavor)}</div>
        ${description ? 
            `<div class="flavor-description">${escapeHtml(description)}</div>` :
            `<div class="flavor-description no-description">No description available</div>`
        }
        <div class="flavor-date">
            <i class="fas fa-calendar-alt"></i>
            ${date}
        </div>
    `;
    return card;
}

// Format date for display
function formatDate(dateString) {
    return dateString || '';
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Auto-refresh functionality (optional)
function startAutoRefresh() {
    // Refresh every 30 minutes
    setInterval(() => {
        console.log('Auto-refreshing flavors...');
        loadFlavors();
    }, 30 * 60 * 1000);
}

// Start auto-refresh after initial load
setTimeout(startAutoRefresh, 5000);
