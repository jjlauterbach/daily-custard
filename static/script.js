// App configuration
const STATIC_FLAVORS_URL = 'data/flavors.json';
const NOMINATIM_API_URL = 'https://nominatim.openstreetmap.org/search';

// State
let userLocation = null;
let userLocationMarker = null;
let mapInstance = null;
let mapMarkers = [];
let allLocations = [];
let filteredLocations = [];
let selectedBrands = new Set(['all']);

// DOM elements
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const errorMessageEl = document.getElementById('errorMessage');
const flavorsGridEl = document.getElementById('flavorsGrid');
const currentDateEl = document.getElementById('currentDate');
const locationStatusEl = document.getElementById('locationStatus');
const mapViewEl = document.getElementById('mapView');
const toggleMapBtn = document.getElementById('toggleMapBtn');

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    setCurrentDateToLocal();
    initializeLocationControls();
    loadSavedCity();
    
    // Check if user wants map shown by default (from localStorage)
    const showMap = localStorage.getItem('showMap') === 'true';
    if (showMap) {
        toggleMap();
    }
    
    loadFlavors();
});

// Set current date in header (simple localized version)
function setCurrentDateToLocal() {
    const now = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    if (currentDateEl) {
        currentDateEl.textContent = now.toLocaleDateString('en-US', options);
    }
}

// Load flavors from static JSON
async function loadFlavors() {
    showLoading();
    
    try {
        const locations = await fetchFlavorsFromStatic();
        
        if (!locations || locations.length === 0) {
            showError('No flavors found for today. Please try again later.');
            return;
        }
        
        allLocations = locations;
        
        // Show filters panel 
        const filtersPanel = document.getElementById('filtersPanel');
        if (filtersPanel) {
            filtersPanel.style.display = 'block';
        }

        applyFiltersAndDisplay(); 
        
    } catch (err) {
        console.error('Error loading flavors:', err);
        showError('Failed to load flavor data. Please try again later.');
    }
}

// Fetch from static JSON file
async function fetchFlavorsFromStatic() {
    const response = await fetch(STATIC_FLAVORS_URL);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    console.log(`Loaded ${data.locations.length} locations from static JSON (generated: ${data.generated_at})`);
    return data.locations;

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

// --- Map Functions ---

function initMap() {
    if (mapInstance) return;

    // Default to Milwaukee area if no user location
    const defaultCenter = [43.0389, -87.9065];
    const center = userLocation ? [userLocation.lat, userLocation.lng] : defaultCenter;

    mapInstance = L.map('mapView').setView(center, 10);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(mapInstance);

    // If we have user location, add a special marker
    if (userLocation) {
        addUserLocationMarker();
    }
}

function addUserLocationMarker() {
    if (!mapInstance || !userLocation) return;
    
    // Remove existing marker if present
    if (userLocationMarker) {
        userLocationMarker.remove();
        userLocationMarker = null;
    }
    
    // Custom icon for user location
    const userIcon = L.divIcon({
        className: 'user-location-marker',
        html: '<i class="fas fa-street-view" style="color: #2563eb; font-size: 24px; text-shadow: 2px 2px 0 #fff; background: white; border-radius: 50%;"></i>',
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    });

    userLocationMarker = L.marker([userLocation.lat, userLocation.lng], {icon: userIcon})
        .addTo(mapInstance)
        .bindPopup("Your Location");
}

function updateMapMarkers(groups) {
    if (!mapInstance) return;

    // Clear existing markers
    mapMarkers.forEach(marker => marker.remove());
    mapMarkers = [];

    const bounds = L.latLngBounds();
    if (userLocation) {
        bounds.extend([userLocation.lat, userLocation.lng]);
    }

    groups.forEach(group => {
        if (group.lat && group.lng) {
            const marker = L.marker([group.lat, group.lng])
                .addTo(mapInstance)
                .bindPopup(`
                    <strong>${escapeHtml(group.name)}</strong><br>
                    ${group.flavors.map(f => `• ${escapeHtml(f.name)}`).join('<br>')}
                `);
            
            mapMarkers.push(marker);
            bounds.extend([group.lat, group.lng]);
        }
    });

    if (mapMarkers.length > 0) {
        mapInstance.fitBounds(bounds, { padding: [50, 50] });
    }
}

function toggleMap() {
    if (mapViewEl.style.display === 'none' || !mapViewEl.style.display) {
        mapViewEl.style.display = 'block';
        toggleMapBtn.classList.add('active');
        toggleMapBtn.innerHTML = '<i class="fas fa-map"></i> Hide Map';
        localStorage.setItem('showMap', 'true');
        
        trackEvent('map_toggle', { action: 'show' });
        
        // Leaflet needs to know it became visible to render correctly
        if (!mapInstance) {
            initMap();
        } else {
            setTimeout(() => mapInstance.invalidateSize(), 100);
        }
    } else {
        mapViewEl.style.display = 'none';
        toggleMapBtn.classList.remove('active');
        toggleMapBtn.innerHTML = '<i class="fas fa-map"></i> Show Map';
        localStorage.setItem('showMap', 'false');
        
        trackEvent('map_toggle', { action: 'hide' });
    }
}

// --- Geocoding & Location ---

async function geocodeLocation(query) {
    if (!query) return;
    
    // Add "WI" to search if not present, to bias towards Wisconsin
    const searchQuery = query.toLowerCase().includes('wi') || query.toLowerCase().includes('wisconsin') 
        ? query 
        : `${query}, WI`;
        
    try {
        updateLocationStatus('Searching...', 'info');
        const response = await fetch(`${NOMINATIM_API_URL}?q=${encodeURIComponent(searchQuery)}&format=json&limit=1`);
        const data = await response.json();
        
        if (data && data.length > 0) {
            const result = data[0];
            const lat = parseFloat(result.lat);
            const lng = parseFloat(result.lon);
            const displayName = result.display_name.split(',').slice(0, 2).join(','); // Shorten address
            
            userLocation = { lat, lng, displayName };
            saveCityName(displayName);
            
            trackEvent('location_search', { search_type: 'manual', query: searchQuery });
            
            // Update map view if active
            if (mapInstance) {
                mapInstance.setView([lat, lng], 12);
                addUserLocationMarker();
            }
            
            updateLocationStatus(displayName, 'success');
            applyFiltersAndDisplay();
        } else {
            updateLocationStatus('Location not found', 'error');
        }
    } catch (error) {
        console.error('Geocoding error:', error);
        updateLocationStatus('Search failed', 'error');
    }
}

function updateLocationStatus(msg, type = 'info') {
    const input = document.getElementById('locationInput');
    
    // For success, update the input field directly instead of showing status text
    if (type === 'success' && input) {
        // Strip prefixes if present
        input.value = msg;
        input.classList.add('has-location');
        input.blur(); // Remove focus to show the static style
        if (locationStatusEl) locationStatusEl.style.display = 'none';
        return;
    }

    // For other states (info/error), show the status text
    if (locationStatusEl) {
        locationStatusEl.textContent = msg;
        locationStatusEl.style.display = 'block';
        locationStatusEl.className = `location-status status-${type}`;
        if (type === 'error') {
            locationStatusEl.style.color = '#ef4444';
        } else if (type === 'success') {
            locationStatusEl.style.color = '#10b981';
        } else {
            locationStatusEl.style.color = '#6b7280';
        }
    }
    
    // If not success, ensure has-location is removed so it looks like an input again
    if (input) {
        input.classList.remove('has-location');
    }
}

function requestGeolocation() {
    if (!navigator.geolocation) {
        alert('Geolocation is not supported by your browser');
        return;
    }
    
    updateLocationStatus('Getting GPS...', 'info');
    
    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            
            userLocation = { 
                lat: lat, 
                lng: lng, 
                displayName: "Current Location" 
            };
            
            trackEvent('location_search', { search_type: 'gps' });
            
            if (mapInstance) {
                mapInstance.setView([lat, lng], 12);
                addUserLocationMarker();
            }
            applyFiltersAndDisplay();
            updateLocationStatus('Current Location', 'success');
            
            // Reverse geocode to get city name and save it
            const cityName = await reverseGeocode(lat, lng);
            if (cityName) {
                userLocation.displayName = cityName;
                saveCityName(cityName);
                updateLocationStatus(cityName, 'success');
            }
        },
        (error) => {
            console.error('Geolocation error:', error);
            updateLocationStatus('GPS Permission Denied', 'error');
        }
    );
}

// Reverse geocode lat/lng to city name
async function reverseGeocode(lat, lng) {
    try {
        const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`
        );
        const data = await response.json();
        
        if (data && data.address) {
            // Try to get city, town, village, or county
            const city = data.address.city || 
                        data.address.town || 
                        data.address.village || 
                        data.address.county;
            const state = data.address.state;
            
            if (city && state) {
                return `${city}, ${state}`;
            } else if (city) {
                return city;
            }
        }
        
        return null;
    } catch (error) {
        console.error('Reverse geocoding error:', error);
        return null;
    }
}

// Load saved city name and geocode it (stores city only, not exact coordinates)
function loadSavedCity() {
    const savedCity = localStorage.getItem('userCity');
    if (savedCity) {
        console.log('Loading saved city:', savedCity);
        // Automatically geocode the saved city to get fresh coordinates
        geocodeLocation(savedCity);
    }
}

// Save city name only (not coordinates) for privacy
function saveCityName(displayName) {
    if (displayName) {
        localStorage.setItem('userCity', displayName);
        console.log('Saved city name:', displayName);
    }
}

// Distance calculation (Haversine formula)
function calculateDistance(lat1, lng1, lat2, lng2) {
    const R = 3959; // Earth's radius in miles
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng/2) * Math.sin(dLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// --- Grouping & Filtering ---

function applyFiltersAndDisplay() {
    // 1. Start with all locations
    const groups = allLocations;
    
    // Get filter values
    const radiusFilter = document.getElementById('radiusFilter');
    const radiusMiles = radiusFilter ? parseFloat(radiusFilter.value) : 10;
    
    // Calculate distances first if we have user location
    if (userLocation) {
        groups.forEach(g => {
            if (g.lat && g.lng) {
                g.distance = calculateDistance(userLocation.lat, userLocation.lng, g.lat, g.lng);
            }
        });
    }

    let filteredGroups = groups.filter(g => {
        // Radius Filter (only applied if we have user location and radius > 0)
        // If radius is 0, we can treat it as "All Distances" usually, or max
        // Here, let's assume specific values. If the select has "0" or "all", handle it.
        // Assuming the select options are like "5", "10", "25", "50", "0" (Any)
        if (radiusMiles > 0 && userLocation) {
            if (g.distance === null || g.distance === undefined || g.distance > radiusMiles) {
                return false;
            }
        }
        
        // Brand Filter (Multi-select)
        if (!selectedBrands.has('all') && !selectedBrands.has(g.brand)) {
            return false;
        }
        
        return true;
    });
    
    // Track filter application
    trackEvent('filters_applied', {
        radius_miles: radiusMiles,
        brand_count: selectedBrands.size,
        has_location: !!userLocation,
        results_count: filteredGroups.length
    });
    
    // Sort logic
    // Default sort: Use nearby if available, otherwise brand
    if (userLocation) {
        filteredGroups.sort((a, b) => (a.distance || 9999) - (b.distance || 9999));
    } else {
        filteredGroups.sort((a, b) => (a.brand || '').localeCompare(b.brand || ''));
    }

    
    // Update map with visible groups
    if (mapInstance) {
        updateMapMarkers(filteredGroups);
    }
    
    displayLocationCards(filteredGroups);
}

// --- Rendering ---

function displayLocationCards(groups) {
    loadingEl.style.display = 'none';
    errorEl.style.display = 'none';
     
    flavorsGridEl.innerHTML = '';
    
    if (groups.length === 0) {
        flavorsGridEl.innerHTML = `
            <div class="no-results">
                <i class="fas fa-search"></i>
                <p>No locations found matching your criteria.</p>
                ${userLocation ? '<p class="sub-text">Try increasing the search radius or changing criteria.</p>' : ''}
            </div>`;
        return;
    }
    
    groups.forEach(group => {
        const card = createLocationCard(group);
        flavorsGridEl.appendChild(card);
    });
}

function createLocationCard(group) {
    const card = document.createElement('div');
    card.className = 'location-card';
    card.id = `card-${group.id}`;

    // Distance Badge
    const distanceHtml = group.distance !== null && group.distance !== undefined
        ? `<div class="distance-badge"><i class="fas fa-location-arrow"></i> ${group.distance.toFixed(1)} mi</div>`
        : '';

    // Header Section
    let headerHtml = `
        <div class="shop-header">
            <div class="shop-info">
                <div>
                    <div class="shop-icon"><i class="fas fa-ice-cream"></i></div>
                    ${distanceHtml}
                </div>
                <div>
                    <div class="shop-name">${escapeHtml(group.brand)}</div>
                    ${group.address ? `<div class="shop-address">${escapeHtml(group.address)}</div>` : ''}
                </div>
            </div>
        </div>
    `;

    // Flavors List
    let flavorsHtml = '<div class="location-flavors">';
    
    group.flavors.forEach(flavor => {
        const description = flavor.description && flavor.description.trim() && 
                           flavor.description !== 'No description available' 
                           ? flavor.description 
                           : '';
                           
        flavorsHtml += `
            <div class="flavor-item">
                <div class="flavor-name">${escapeHtml(flavor.name)}</div>
                <div class="flavor-description">${escapeHtml(description)}</div>
            </div>
        `;
    });
    
    flavorsHtml += '</div>'; // close location-flavors

    // Footer / Links
    let footerHtml = '';
    if (group.url || group.address) {
        footerHtml = `
            <div class="card-footer">
                ${group.url ? `<a href="${group.url}" target="_blank" class="flavor-link footer-link" onclick="trackEvent('external_link', {link_type: 'website', brand: '${escapeHtml(group.brand)}'});"><i class="fas fa-external-link-alt"></i> Website</a>` : ''}
                ${group.address ? `<a href="https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(group.address)}" target="_blank" class="flavor-link footer-link" onclick="trackEvent('external_link', {link_type: 'directions', brand: '${escapeHtml(group.brand)}'});"><i class="fas fa-directions"></i> Directions</a>` : ''}
            </div>
        `;
    }

    card.innerHTML = headerHtml + flavorsHtml + footerHtml;
    return card;
}


// --- Initialization Helpers ---

function initializeLocationControls() {
    const useLocationBtn = document.getElementById('useLocationBtn');
    const locationInput = document.getElementById('locationInput');
    const searchInput = document.getElementById('searchInput');
    // const brandFilter = document.getElementById('brandFilter'); // Removed
    const sortBy = document.getElementById('sortBy');
    const radiusFilter = document.getElementById('radiusFilter');
    
    if (toggleMapBtn) {
        toggleMapBtn.addEventListener('click', toggleMap);
    }

    if (useLocationBtn) {
        useLocationBtn.addEventListener('click', requestGeolocation);
    }
    
    if (locationInput) {
        locationInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                geocodeLocation(locationInput.value);
            }
        });
        
        // When clicking the "set" input, clear it or reset state to allow editing
        locationInput.addEventListener('click', () => {
            if (locationInput.classList.contains('has-location')) {
                locationInput.classList.remove('has-location');
                locationInput.select(); // Select all text for easy replacement
            }
        });
        
        // Also handle focus in cases like tabbing
         locationInput.addEventListener('focus', () => {
             if (locationInput.classList.contains('has-location')) {
                 locationInput.classList.remove('has-location');
                 locationInput.select();
             }
         });
    }
    
    // --- Filter Modal Logic ---
    const openFiltersBtn = document.getElementById('openFiltersBtn');
    const filterModal = document.getElementById('filterModal');
    const closeModalBtn = document.getElementById('closeModalBtn');
    const modalSelectAllBtn = document.getElementById('modalSelectAllBtn');
    const modalApplyBtn = document.getElementById('modalApplyBtn');
    const modalBrandGrid = document.getElementById('modalBrandGrid');

    if (openFiltersBtn && filterModal) {
        // Open Modal
        openFiltersBtn.addEventListener('click', () => {
            syncModalCheckboxes();
            filterModal.classList.add('active');
            document.body.style.overflow = 'hidden'; // Prevent background scrolling
        });

        // Close Modal Handlers
        function closeModal() {
            filterModal.classList.remove('active');
            document.body.style.overflow = '';
        }

        if (closeModalBtn) closeModalBtn.addEventListener('click', closeModal);
        
        filterModal.addEventListener('click', (e) => {
            if (e.target === filterModal) closeModal();
        });

        // Select All
        if (modalSelectAllBtn) {
            modalSelectAllBtn.addEventListener('click', () => {
                const checkboxes = modalBrandGrid.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(cb => cb.checked = true);
            });
        }

        // Apply Filters
        if (modalApplyBtn) {
            modalApplyBtn.addEventListener('click', () => {
                const checkboxes = modalBrandGrid.querySelectorAll('input[type="checkbox"]');
                const checked = Array.from(checkboxes).filter(cb => cb.checked);
                const allCheckboxCount = checkboxes.length;
                
                selectedBrands.clear();
                
                // If all are checked, use 'all' sentinel for efficiency/logic, 
                // OR if very few are unchecked, we could just list them all.
                // Current logic uses 'all' sentinel. Let's stick to that if all are checked.
                if (checked.length === allCheckboxCount) {
                    selectedBrands.add('all');
                } else if (checked.length === 0) {
                    // If none checked, arguably show none, or reset to all?
                    // Let's force at least one selection or default to all.
                    // For now, let's allow "none" (empty map)
                } else {
                    checked.forEach(cb => selectedBrands.add(cb.value));
                }

                updateBrandButtonText();
                applyFiltersAndDisplay();
                closeModal();
            });
        }
    }

    function syncModalCheckboxes() {
        const checkboxes = modalBrandGrid.querySelectorAll('input[type="checkbox"]');
        const isAll = selectedBrands.has('all');

        checkboxes.forEach(cb => {
            if (isAll) {
                cb.checked = true;
            } else {
                cb.checked = selectedBrands.has(cb.value);
            }
        });
    }

    function updateBrandButtonText() {
        const span = openFiltersBtn.querySelector('span');
        if (selectedBrands.has('all')) {
            span.textContent = 'All Brands';
        } else {
            const count = selectedBrands.size;
            span.textContent = `${count} Brand${count !== 1 ? 's' : ''}`;
        }
    }
    
    if (sortBy) {
        sortBy.addEventListener('change', () => applyFiltersAndDisplay());
    }
    
    if (radiusFilter) {
        radiusFilter.addEventListener('change', () => applyFiltersAndDisplay());
    }
}

// Format date for display
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    return date.toLocaleDateString();
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.innerText = text;
    return div.innerHTML;
}

// Analytics helper
function trackEvent(eventName, eventParams = {}) {
    if (typeof gtag !== 'undefined') {
        gtag('event', eventName, eventParams);
    }
}
