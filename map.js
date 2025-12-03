// Enhanced QuickHireMap with proper loading state management and interactive actions
class QuickHireMap {
    constructor(config) {
        this.config = config;
        this.map = null;
        this.markers = [];
        this.userMarker = null;
        this.radiusCircle = null;
        this.isLocating = false;
        this.isSearching = false;
        this.currentLocation = null;
        this.loadingStates = {
            map: false,
            location: false,
            search: false
        };
        this.init();
    }

    init() {
        this.initializeMap();
        this.setupEventListeners();
        this.setupSearchForm();
        this.loadInitialData();
    }

    initializeMap() {
        try {
            // Check if map container exists
            const mapContainer = document.getElementById('map');
            if (!mapContainer) {
                throw new Error('Map container not found');
            }

            // Check if Leaflet is available
            if (typeof L === 'undefined') {
                throw new Error('Map library not loaded');
            }

            const defaultLat = this.config.userLat || 20.5937;
            const defaultLng = this.config.userLng || 78.9629;
            const defaultZoom = this.config.userLat ? 12 : 5;

            this.map = L.map('map', {
                zoomControl: true,
                zoomAnimation: true,
                fadeAnimation: true,
                markerZoomAnimation: true
            }).setView([defaultLat, defaultLng], defaultZoom);

            // Add error handling for tile layer
            this.addTileLayer();
            this.addMapControls();

            console.log('Map initialized successfully');
            
            // Hide any error messages
            if (typeof hideMapError === 'function') {
                hideMapError();
            }

        } catch (error) {
            console.error('Map initialization failed:', error);
            
            // Show user-friendly error message
            if (typeof showMapError === 'function') {
                let errorMessage = 'Unable to load map. ';
                
                if (error.message.includes('container not found')) {
                    errorMessage += 'Map container missing.';
                } else if (error.message.includes('library not loaded')) {
                    errorMessage += 'Map library failed to load. Please check your internet connection.';
                } else {
                    errorMessage += 'Please check your internet connection or try again later.';
                }
                
                showMapError(errorMessage);
            }
            
            // Ensure loading overlay is hidden
            this.hideAllLoadingStates();
        }
    }

    addTileLayer() {
        try {
            const tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 18,
                minZoom: 3
            });

            tileLayer.addTo(this.map);
            
            tileLayer.on('load', () => {
                console.log('Map tiles loaded');
                this.hideAllLoadingStates();
            });

            tileLayer.on('tileerror', (error) => {
                console.warn('Tile loading error:', error);
                this.showNotification('Map tiles failed to load. Some features may not work properly.', 'warning');
            });

        } catch (error) {
            console.error('Tile layer error:', error);
            this.showNotification('Failed to load map tiles. Using fallback mode.', 'warning');
        }
    }

    addMapControls() {
        L.control.scale({ imperial: false }).addTo(this.map);
        this.addLocationControl();
    }

    setupEventListeners() {
        this.map.on('load', () => {
            console.log('Map fully loaded');
            this.hideAllLoadingStates();
        });

        this.map.on('locationerror', (e) => {
            console.error('Map location error:', e.message);
            this.showNotification('Could not determine your location. Please try manual search.', 'error');
            this.hideAllLoadingStates();
        });

        this.map.on('locationfound', (e) => {
            console.log('Location found via map:', e.latlng);
            this.handleLocationFound(e);
            this.hideAllLoadingStates();
        });
    }

    setupSearchForm() {
        const searchForm = document.getElementById('mapFilterForm');
        if (searchForm) {
            searchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleSearch();
            });
        }

        // Current location button
        const currentLocationBtn = document.getElementById('getCurrentLocation');
        if (currentLocationBtn) {
            currentLocationBtn.addEventListener('click', () => {
                this.getCurrentLocation();
            });
        }

        // Auto-search when filters change (if we have a location)
        const radiusSelect = document.getElementById('radiusSelect');
        const skillSelect = document.getElementById('skillSelect');
        
        [radiusSelect, skillSelect].forEach(element => {
            if (element) {
                element.addEventListener('change', () => {
                    if (this.currentLocation && !this.isSearching) {
                        clearTimeout(this.searchTimeout);
                        this.searchTimeout = setTimeout(() => {
                            this.handleSearch();
                        }, 500);
                    }
                });
            }
        });
    }

    loadInitialData() {
        // Load initial markers if we have user location
        if (this.config.userLat && this.config.userLng) {
            this.currentLocation = {
                lat: this.config.userLat,
                lng: this.config.userLng
            };
            this.addUserLocationMarker();
            this.loadMarkersForCurrentLocation();
        } else {
            this.showInstructionMessage();
        }
        
        // Ensure loading states are hidden
        setTimeout(() => this.hideAllLoadingStates(), 1000);
    }

    async handleSearch() {
        if (this.isSearching) {
            console.log('Search already in progress');
            return;
        }

        const locationInput = document.getElementById('locationInput');
        const location = locationInput.value.trim();
        const radius = document.getElementById('radiusSelect').value;
        const skill = document.getElementById('skillSelect').value;

        if (!location) {
            this.showNotification('Please enter a location to search', 'error');
            return;
        }

        this.isSearching = true;
        this.loadingStates.search = true;
        this.showSearchLoading(true);

        try {
            let coords;

            if (location.toLowerCase().includes('current')) {
                coords = await this.getCurrentPosition();
            } else {
                coords = await this.geocodeLocation(location);
            }

            if (coords) {
                this.currentLocation = coords;
                await this.performSearch(coords.lat, coords.lng, radius, skill);
                
                document.getElementById('hiddenLat').value = coords.lat;
                document.getElementById('hiddenLng').value = coords.lng;
                
                if (location.toLowerCase().includes('current')) {
                    locationInput.value = 'Current Location';
                }
            }

        } catch (error) {
            console.error('Search error:', error);
            this.showNotification(error.message, 'error');
        } finally {
            this.isSearching = false;
            this.loadingStates.search = false;
            this.showSearchLoading(false);
            this.hideAllLoadingStates();
        }
    }

    async geocodeLocation(locationName) {
        try {
            console.log('Geocoding location:', locationName);
            const response = await fetch(`/api/geocode?location=${encodeURIComponent(locationName)}`);
            
            if (!response.ok) {
                throw new Error(`Geocoding failed: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            if (!data.latitude || !data.longitude) {
                throw new Error('No coordinates found for this location');
            }

            return {
                lat: data.latitude,
                lng: data.longitude,
                location: data.location || locationName
            };

        } catch (error) {
            console.error('Geocoding error:', error);
            throw new Error(`Location not found: ${locationName}. Please try a different location.`);
        }
    }

    getCurrentPosition() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('Geolocation is not supported by your browser'));
                return;
            }

            this.loadingStates.location = true;
            this.showLocationLoading(true);

            const options = {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 300000
            };

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    this.hideAllLoadingStates();
                    resolve({
                        lat: position.coords.latitude,
                        lng: position.coords.longitude,
                        accuracy: position.coords.accuracy
                    });
                },
                (error) => {
                    this.hideAllLoadingStates();
                    let errorMessage = 'Could not get your location. ';
                    
                    switch (error.code) {
                        case error.PERMISSION_DENIED:
                            errorMessage += 'Please allow location access and try again.';
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMessage += 'Location information is unavailable.';
                            break;
                        case error.TIMEOUT:
                            errorMessage += 'Location request timed out.';
                            break;
                        default:
                            errorMessage += 'An unknown error occurred.';
                    }
                    
                    reject(new Error(errorMessage));
                },
                options
            );
        });
    }

    async getCurrentLocation() {
        if (this.isLocating) {
            console.log('Location request already in progress');
            return;
        }

        this.isLocating = true;
        this.loadingStates.location = true;
        this.showLocationLoading(true);

        try {
            const position = await this.getCurrentPosition();
            this.currentLocation = position;
            
            document.getElementById('locationInput').value = 'Current Location';
            document.getElementById('hiddenLat').value = position.lat;
            document.getElementById('hiddenLng').value = position.lng;
            
            const radius = document.getElementById('radiusSelect').value;
            const skill = document.getElementById('skillSelect').value;
            await this.performSearch(position.lat, position.lng, radius, skill);
            
        } catch (error) {
            console.error('Current location error:', error);
            this.showNotification(error.message, 'error');
            document.getElementById('locationInput').focus();
        } finally {
            this.isLocating = false;
            this.loadingStates.location = false;
            this.hideAllLoadingStates();
        }
    }

    async performSearch(lat, lng, radius, skill) {
        try {
            console.log('Performing search:', { lat, lng, radius, skill });
            
            const params = new URLSearchParams({
                lat: lat,
                lng: lng,
                radius: radius,
                skill: skill
            });

            const response = await fetch(`/api/search/map?${params}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Search failed');
            }

            if (data.error) {
                throw new Error(data.error);
            }

            this.updateMapWithResults(data, lat, lng, radius);
            
            if (data.count > 0) {
                this.showNotification(`Found ${data.count} ${data.type} nearby`, 'success');
            } else {
                this.showNotification(`No ${data.type} found in this area. Try increasing search radius.`, 'info');
            }

        } catch (error) {
            console.error('Search performance error:', error);
            throw new Error(`Search failed: ${error.message}`);
        } finally {
            this.hideAllLoadingStates();
        }
    }

    updateMapWithResults(data, lat, lng, radius) {
        this.clearMarkers();
        this.updateUserLocation(lat, lng, radius);
        this.addSearchResultsMarkers(data.items, data.type);
        this.updateResultsList(data.items, data.type);
        this.adjustMapView(data.items, lat, lng);
        this.hideAllLoadingStates();
    }

    clearMarkers() {
        this.markers.forEach(marker => {
            if (marker && this.map.hasLayer(marker)) {
                this.map.removeLayer(marker);
            }
        });
        this.markers = [];
    }

    updateUserLocation(lat, lng, radius) {
        if (this.userMarker) {
            this.map.removeLayer(this.userMarker);
        }
        if (this.radiusCircle) {
            this.map.removeLayer(this.radiusCircle);
        }

        const userIcon = L.divIcon({
            className: 'user-location-marker',
            html: `
                <div style="
                    background: #4361ee;
                    border: 3px solid white;
                    border-radius: 50%;
                    width: 20px;
                    height: 20px;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                "></div>
            `,
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        });

        this.userMarker = L.marker([lat, lng], { icon: userIcon })
            .addTo(this.map)
            .bindPopup(`
                <div class="text-center">
                    <strong>Your Location</strong><br>
                    <small>Searching within ${radius} km</small>
                </div>
            `);

        this.radiusCircle = L.circle([lat, lng], {
            color: '#4361ee',
            fillColor: '#4361ee',
            fillOpacity: 0.1,
            weight: 2,
            radius: radius * 1000
        }).addTo(this.map);

        setTimeout(() => {
            this.userMarker.openPopup();
        }, 1000);
    }

    // Enhanced marker creation with better event handling
    addSearchResultsMarkers(items, type) {
        const isJobs = type === 'jobs';
        
        items.forEach(item => {
            if (!item.lat || !item.lng) return;

            const icon = L.divIcon({
                className: 'result-marker interactive',
                html: `
                    <div style="
                        background: ${isJobs ? '#4361ee' : '#06d6a0'};
                        border: 2px solid white;
                        border-radius: 50%;
                        width: 40px;
                        height: 40px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-size: 16px;
                        font-weight: bold;
                        box-shadow: 0 3px 8px rgba(0,0,0,0.3);
                        cursor: pointer;
                        transition: all 0.3s ease;
                    " title="${isJobs ? 'Job: ' + this.escapeHtml(item.title) : 'Seeker: ' + this.escapeHtml(item.name)}">
                        ${isJobs ? '💼' : '👤'}
                    </div>
                `,
                iconSize: [40, 40],
                iconAnchor: [20, 40]
            });

            const marker = L.marker([item.lat, item.lng], { 
                icon: icon,
                riseOnHover: true
            }).addTo(this.map);

            // Create popup content
            const popupContent = this.createPopupContent(item, isJobs);
            marker.bindPopup(popupContent, {
                maxWidth: 300,
                minWidth: 250,
                className: 'custom-map-popup'
            });

            marker.itemId = item.id;
            marker.itemType = type;
            this.markers.push(marker);

            // Enhanced click handling
            marker.on('click', (e) => {
                this.highlightListItem(item.id, isJobs ? 'job' : 'seeker');
                
                setTimeout(() => {
                    this.attachPopupEventHandlers(marker, item, isJobs);
                }, 100);
            });

            // Hover effects
            marker.on('mouseover', () => {
                const iconElement = marker.getElement().querySelector('.result-marker div');
                if (iconElement) {
                    iconElement.style.transform = 'scale(1.1)';
                    iconElement.style.boxShadow = '0 4px 12px rgba(0,0,0,0.4)';
                }
            });

            marker.on('mouseout', () => {
                const iconElement = marker.getElement().querySelector('.result-marker div');
                if (iconElement) {
                    iconElement.style.transform = 'scale(1)';
                    iconElement.style.boxShadow = '0 3px 8px rgba(0,0,0,0.3)';
                }
            });
        });
        
        this.hideAllLoadingStates();
    }

    createPopupContent(item, isJob) {
        if (isJob) {
            return `
                <div class="map-popup-content">
                    <h6 class="fw-bold mb-2">${this.escapeHtml(item.title)}</h6>
                    <p class="mb-1 small text-muted">
                        <i class="fas fa-building me-1"></i>${this.escapeHtml(item.employer)}
                    </p>
                    <p class="mb-1 small text-muted">
                        <i class="fas fa-map-marker-alt me-1"></i>${this.escapeHtml(item.location)}
                    </p>
                    <p class="mb-1 small text-muted">
                        <i class="fas fa-rupee-sign me-1"></i>₹${item.pay}
                    </p>
                    <p class="mb-2 small text-muted">
                        <i class="fas fa-tools me-1"></i>${this.escapeHtml(item.skills)}
                    </p>
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="badge bg-primary">${item.distance} km away</span>
                        <button class="btn btn-primary btn-sm apply-btn" 
                                data-job-id="${item.id}" 
                                data-job-title="${this.escapeHtml(item.title)}">
                            <i class="fas fa-paper-plane me-1"></i>Apply
                        </button>
                    </div>
                    <div class="mt-2 text-center">
                        <a href="/apply_job/${item.id}" class="small text-muted">View Full Details</a>
                    </div>
                </div>
            `;
        } else {
            return `
                <div class="map-popup-content">
                    <h6 class="fw-bold mb-2">${this.escapeHtml(item.name)}</h6>
                    <p class="mb-1 small text-muted">
                        <i class="fas fa-tools me-1"></i>${this.escapeHtml(item.skills)}
                    </p>
                    <p class="mb-1 small text-muted">
                        <i class="fas fa-map-marker-alt me-1"></i>${this.escapeHtml(item.location)}
                    </p>
                    ${item.experience ? `
                    <p class="mb-1 small text-muted">
                        <i class="fas fa-briefcase me-1"></i>${item.experience} years experience
                    </p>` : ''}
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="badge bg-primary">${item.distance} km away</span>
                    </div>
                    <div class="d-flex gap-1">
                        <button class="btn btn-primary btn-sm flex-fill chat-btn"
                                data-seeker-id="${item.id}" 
                                data-seeker-name="${this.escapeHtml(item.name)}">
                            <i class="fas fa-comment me-1"></i>Chat
                        </button>
                        <button class="btn btn-success btn-sm flex-fill hire-btn"
                                data-seeker-id="${item.id}" 
                                data-seeker-name="${this.escapeHtml(item.name)}">
                            <i class="fas fa-user-check me-1"></i>Hire
                        </button>
                    </div>
                    <div class="mt-2 text-center">
                        <a href="/profile/${this.getSeekerUserId(item.id)}" class="small text-muted">View Profile</a>
                    </div>
                </div>
            `;
        }
    }

    attachPopupEventHandlers(marker, item, isJob) {
        const popup = marker.getPopup();
        const popupElement = popup.getElement();
        
        if (!popupElement) return;

        if (isJob) {
            const applyBtn = popupElement.querySelector('.apply-btn');
            if (applyBtn) {
                applyBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.handleMapApply(item.id, item.title);
                });
            }
        } else {
            const chatBtn = popupElement.querySelector('.chat-btn');
            const hireBtn = popupElement.querySelector('.hire-btn');
            
            if (chatBtn) {
                chatBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.handleMapChat(item.id, item.name);
                });
            }
            
            if (hireBtn) {
                hireBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.handleMapHire(item.id, item.name);
                });
            }
        }
    }

    // Enhanced action handlers
    async handleMapApply(jobId, jobTitle) {
        if (!confirm(`Are you sure you want to apply for "${jobTitle}"?`)) {
            return;
        }

        try {
            this.showNotification('Submitting application...', 'info');
            
            const response = await fetch(`/api/map/apply/${jobId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification(data.message, 'success');
                this.updateJobApplicationStatus(jobId, true);
                this.closePopupForJob(jobId);
            } else {
                this.showNotification(data.message, 'error');
            }

        } catch (error) {
            console.error('Apply error:', error);
            this.showNotification('Failed to submit application. Please try again.', 'error');
        }
    }

    async handleMapHire(seekerId, seekerName) {
        if (!confirm(`Are you sure you want to hire "${seekerName}"?`)) {
            return;
        }

        try {
            this.showNotification('Processing hire request...', 'info');
            
            const response = await fetch(`/api/map/hire/${seekerId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification(data.message, 'success');
                this.updateSeekerHireStatus(seekerId, true);
                this.closePopupForSeeker(seekerId);
            } else {
                this.showNotification(data.message, 'error');
            }

        } catch (error) {
            console.error('Hire error:', error);
            this.showNotification('Failed to complete hire. Please try again.', 'error');
        }
    }

    async handleMapChat(seekerId, seekerName) {
        try {
            this.showNotification('Starting chat...', 'info');
            
            const response = await fetch(`/api/map/start_chat/${seekerId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification(data.message, 'success');
                
                setTimeout(() => {
                    if (data.redirect_url) {
                        window.location.href = data.redirect_url;
                    } else {
                        window.location.href = `/chat/room/${data.room_id}`;
                    }
                }, 1500);
                
            } else {
                this.showNotification(data.message, 'error');
            }

        } catch (error) {
            console.error('Chat error:', error);
            this.showNotification('Failed to start chat. Please try again.', 'error');
        }
    }

    updateJobApplicationStatus(jobId, applied) {
        // Update marker popup content
        this.markers.forEach(marker => {
            if (marker.itemId === jobId && marker.itemType === 'jobs') {
                const newContent = marker.getPopup().getContent();
                const updatedContent = newContent.replace(
                    'btn btn-primary btn-sm',
                    'btn btn-success btn-sm disabled'
                ).replace(
                    'Apply',
                    '✓ Applied'
                );
                marker.setPopupContent(updatedContent);
            }
        });

        // Update list item
        const jobItem = document.querySelector(`[data-job-id="${jobId}"]`);
        if (jobItem) {
            const applyBtn = jobItem.querySelector('a[href*="apply_job"]');
            if (applyBtn) {
                applyBtn.classList.remove('btn-primary-modern');
                applyBtn.classList.add('btn-success-modern', 'disabled');
                applyBtn.innerHTML = '<i class="fas fa-check me-1"></i>Applied';
                applyBtn.style.pointerEvents = 'none';
            }
        }
    }

    updateSeekerHireStatus(seekerId, hired) {
        // Update marker popup content
        this.markers.forEach(marker => {
            if (marker.itemId === seekerId && marker.itemType === 'seekers') {
                const newContent = marker.getPopup().getContent();
                const updatedContent = newContent.replace(
                    'btn btn-success btn-sm flex-fill',
                    'btn btn-secondary btn-sm flex-fill disabled'
                ).replace(
                    'Hire',
                    '✓ Hired'
                );
                marker.setPopupContent(updatedContent);
            }
        });

        // Update list item
        const seekerItem = document.querySelector(`[data-seeker-id="${seekerId}"]`);
        if (seekerItem) {
            const hireBtn = seekerItem.querySelector('.hire-btn');
            if (hireBtn) {
                hireBtn.classList.remove('btn-success-modern');
                hireBtn.classList.add('btn-secondary-modern', 'disabled');
                hireBtn.innerHTML = '<i class="fas fa-check me-1"></i>Hired';
                hireBtn.style.pointerEvents = 'none';
            }
        }
    }

    closePopupForJob(jobId) {
        this.markers.forEach(marker => {
            if (marker.itemId === jobId && marker.itemType === 'jobs') {
                marker.closePopup();
            }
        });
    }

    closePopupForSeeker(seekerId) {
        this.markers.forEach(marker => {
            if (marker.itemId === seekerId && marker.itemType === 'seekers') {
                marker.closePopup();
            }
        });
    }

    getSeekerUserId(seekerId) {
        return seekerId; // You might want to enhance this based on your data structure
    }

    updateResultsList(items, type) {
        const isJobs = type === 'jobs';
        const listContainer = document.getElementById(isJobs ? 'jobsList' : 'seekersList');
        const countElement = document.querySelector(isJobs ? '.card-header-modern h5' : '.card-header-modern h5');
        
        if (!listContainer) return;

        if (countElement) {
            countElement.innerHTML = `<i class="fas fa-list me-2"></i>${isJobs ? 'Jobs' : 'Seekers'} (${items.length})`;
        }

        if (items.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-${isJobs ? 'briefcase' : 'users'} fa-3x text-muted mb-3"></i>
                    <p class="text-muted mb-1">No ${isJobs ? 'jobs' : 'job seekers'} found</p>
                    <p class="text-muted small">Try increasing search radius or changing filters</p>
                </div>
            `;
        } else {
            listContainer.innerHTML = items.map(item => this.createListItem(item, isJobs)).join('');
            this.setupListInteractions(isJobs);
        }
        
        this.hideAllLoadingStates();
    }

    createListItem(item, isJob) {
        if (isJob) {
            return `
                <div class="job-item mb-3 p-3 border rounded" 
                     data-job-id="${item.id}"
                     data-lat="${item.lat}" 
                     data-lng="${item.lng}">
                    <h6 class="fw-bold mb-1">${this.escapeHtml(item.title)}</h6>
                    <p class="small text-muted mb-1">
                        <i class="fas fa-building me-1"></i>${this.escapeHtml(item.employer)}
                    </p>
                    <p class="small text-muted mb-1">
                        <i class="fas fa-map-marker-alt me-1"></i>${this.escapeHtml(item.location)}
                    </p>
                    <p class="small text-muted mb-2">
                        <i class="fas fa-rupee-sign me-1"></i>₹${item.pay}
                    </p>
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="badge bg-primary">${item.distance} km away</span>
                        <a href="${item.applyUrl}" class="btn-modern btn-primary-modern btn-sm apply-list-btn">
                            Apply Now
                        </a>
                    </div>
                </div>
            `;
        } else {
            return `
                <div class="seeker-item mb-3 p-3 border rounded" 
                     data-seeker-id="${item.id}"
                     data-lat="${item.lat}" 
                     data-lng="${item.lng}">
                    <h6 class="fw-bold mb-1">${this.escapeHtml(item.name)}</h6>
                    <p class="small text-muted mb-1">
                        <i class="fas fa-tools me-1"></i>${this.escapeHtml(item.skills)}
                    </p>
                    <p class="small text-muted mb-1">
                        <i class="fas fa-map-marker-alt me-1"></i>${this.escapeHtml(item.location)}
                    </p>
                    ${item.experience ? `<p class="small text-muted mb-2">
                        <i class="fas fa-briefcase me-1"></i>${item.experience} years experience
                    </p>` : ''}
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="badge bg-primary">${item.distance} km away</span>
                        <div>
                            <a href="/start_chat/${item.id}" class="btn-modern btn-primary-modern btn-sm me-1 chat-list-btn">
                                <i class="fas fa-comment me-1"></i>Chat
                            </a>
                            <button class="btn-modern btn-success-modern btn-sm hire-list-btn"
                                    data-seeker-id="${item.id}"
                                    data-seeker-name="${this.escapeHtml(item.name)}">
                                <i class="fas fa-user-check me-1"></i>Hire
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    setupListInteractions(isJobs) {
        const selector = isJobs ? '.job-item' : '.seeker-item';
        const type = isJobs ? 'job' : 'seeker';
        
        document.querySelectorAll(selector).forEach(item => {
            item.addEventListener('click', () => {
                const itemId = parseInt(item.getAttribute(`data-${type}-id`));
                this.focusOnMarker(itemId);
            });
        });

        if (!isJobs) {
            document.querySelectorAll('.hire-list-btn').forEach(button => {
                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const seekerId = button.getAttribute('data-seeker-id');
                    const seekerName = button.getAttribute('data-seeker-name');
                    this.handleMapHire(seekerId, seekerName);
                });
            });

            document.querySelectorAll('.chat-list-btn').forEach(button => {
                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const seekerId = button.getAttribute('href').split('/').pop();
                    const seekerName = button.closest('.seeker-item').querySelector('h6').textContent;
                    this.handleMapChat(seekerId, seekerName);
                });
            });
        } else {
            document.querySelectorAll('.apply-list-btn').forEach(button => {
                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const jobId = button.getAttribute('href').split('/').pop();
                    const jobTitle = button.closest('.job-item').querySelector('h6').textContent;
                    this.handleMapApply(jobId, jobTitle);
                });
            });
        }
    }

    adjustMapView(items, userLat, userLng) {
        if (items.length === 0) {
            this.map.setView([userLat, userLng], 12);
        } else {
            const bounds = L.latLngBounds([[userLat, userLng]]);
            items.forEach(item => {
                if (item.lat && item.lng) {
                    bounds.extend([item.lat, item.lng]);
                }
            });

            this.map.fitBounds(bounds, { 
                padding: [50, 50],
                maxZoom: 15,
                animate: true,
                duration: 1
            });
        }
        
        setTimeout(() => this.hideAllLoadingStates(), 500);
    }

    // Enhanced Loading State Management
    hideAllLoadingStates() {
        this.loadingStates.map = false;
        this.loadingStates.location = false;
        this.loadingStates.search = false;
        
        this.showLocationLoading(false);
        this.showSearchLoading(false);
        
        const loadingOverlay = document.getElementById('mapLoadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
        
        const searchButton = document.querySelector('#mapFilterForm button[type="submit"]');
        if (searchButton) {
            searchButton.classList.remove('search-loading');
        }
        
        console.log('All loading states cleared');
    }

    showSearchLoading(show) {
        const searchButton = document.querySelector('#mapFilterForm button[type="submit"]');
        if (searchButton) {
            if (show) {
                searchButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Searching...';
                searchButton.disabled = true;
                searchButton.classList.add('search-loading');
            } else {
                searchButton.innerHTML = '<i class="fas fa-search me-2"></i>Search on Map';
                searchButton.disabled = false;
                searchButton.classList.remove('search-loading');
            }
        }
    }

    showLocationLoading(show) {
        const overlay = document.getElementById('mapLoadingOverlay');
        if (overlay) {
            if (show) {
                overlay.style.display = 'flex';
                overlay.innerHTML = `
                    <div class="text-center text-white">
                        <div class="spinner-border spinner-border-lg mb-3" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p class="h6 mb-1">Getting Your Location</p>
                        <p class="small mb-0">Please allow location access...</p>
                    </div>
                `;
            } else {
                overlay.style.display = 'none';
                overlay.innerHTML = '';
            }
        }
    }

    focusOnMarker(itemId) {
        const marker = this.markers.find(m => m.itemId === itemId);
        if (marker) {
            this.map.setView(marker.getLatLng(), 15, {
                animate: true,
                duration: 0.5
            });
            marker.openPopup();
            this.highlightListItem(itemId, marker.itemType === 'jobs' ? 'job' : 'seeker');
        }
    }

    highlightListItem(itemId, type) {
        document.querySelectorAll(`.${type}-item`).forEach(item => {
            item.classList.remove('active');
        });

        const targetItem = document.querySelector(`[data-${type}-id="${itemId}"]`);
        if (targetItem) {
            targetItem.classList.add('active');
            targetItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    // Enhanced notification system
    showNotification(message, type = 'info') {
        document.querySelectorAll('.quickhire-notification').forEach(alert => alert.remove());

        const iconMap = {
            'success': 'check-circle',
            'error': 'exclamation-triangle',
            'info': 'info-circle',
            'warning': 'exclamation-circle'
        };

        const notification = document.createElement('div');
        notification.className = `quickhire-notification alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = `
            top: 20px; 
            right: 20px; 
            z-index: 1060; 
            min-width: 300px; 
            max-width: 400px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border: none;
            border-radius: 8px;
        `;
        
        notification.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-${iconMap[type] || 'info-circle'} me-2"></i>
                <span class="flex-grow-1">${message}</span>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        const duration = type === 'error' ? 8000 : 5000;
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, duration);
    }

    showInstructionMessage() {
        const listContainer = document.getElementById('jobsList') || document.getElementById('seekersList');
        if (listContainer) {
            listContainer.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-map-marked-alt fa-3x text-primary mb-3"></i>
                    <h6 class="fw-bold mb-2">Find Opportunities Nearby</h6>
                    <p class="text-muted small mb-3">
                        Enter your location or use current location to discover nearby 
                        ${this.config.jobs ? 'job opportunities' : 'skilled workers'}
                    </p>
                    <button class="btn btn-primary" onclick="locateUser()">
                        <i class="fas fa-location-arrow me-2"></i>Use Current Location
                    </button>
                </div>
            `;
        }
    }

    addLocationControl() {
        const locationControl = L.control({ position: 'topleft' });
        
        locationControl.onAdd = (map) => {
            const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
            container.innerHTML = `
                <a href="#" title="Find my location" style="
                    display: block; 
                    width: 30px; 
                    height: 30px; 
                    line-height: 30px; 
                    text-align: center;
                    background: white;
                    border-radius: 4px;
                    box-shadow: 0 1px 5px rgba(0,0,0,0.4);
                ">
                    <i class="fas fa-location-arrow" style="color: #4361ee;"></i>
                </a>
            `;
            
            container.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.getCurrentLocation();
            });
            
            return container;
        };
        
        locationControl.addTo(this.map);
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    handleLocationFound(e) {
        this.currentLocation = e.latlng;
        this.addUserLocationMarker();
    }

    addUserLocationMarker() {
        if (!this.currentLocation) return;
        
        this.updateUserLocation(
            this.currentLocation.lat, 
            this.currentLocation.lng, 
            document.getElementById('radiusSelect').value
        );
    }

    loadMarkersForCurrentLocation() {
        if (!this.currentLocation) return;
        
        const radius = document.getElementById('radiusSelect').value;
        const skill = document.getElementById('skillSelect').value;
        
        this.performSearch(
            this.currentLocation.lat,
            this.currentLocation.lng,
            radius,
            skill
        );
    }

    // Public methods
    locateUser() {
        this.getCurrentLocation();
    }

    resetMap() {
        this.clearMarkers();
        if (this.userMarker) this.map.removeLayer(this.userMarker);
        if (this.radiusCircle) this.map.removeLayer(this.radiusCircle);
        
        document.getElementById('mapFilterForm').reset();
        document.getElementById('hiddenLat').value = '';
        document.getElementById('hiddenLng').value = '';
        
        this.map.setView([20.5937, 78.9629], 5);
        this.currentLocation = null;
        
        this.showInstructionMessage();
        this.hideAllLoadingStates();
        
        this.showNotification('Map has been reset', 'info');
    }
}

// Global functions for backward compatibility
async function handleMapApply(jobId, jobTitle) {
    if (window.quickHireMap) {
        await window.quickHireMap.handleMapApply(jobId, jobTitle);
    }
}

async function handleMapHire(seekerId, seekerName) {
    if (window.quickHireMap) {
        await window.quickHireMap.handleMapHire(seekerId, seekerName);
    }
}

async function handleMapChat(seekerId, seekerName) {
    if (window.quickHireMap) {
        await window.quickHireMap.handleMapChat(seekerId, seekerName);
    }
}

function locateUser() {
    if (window.quickHireMap) {
        window.quickHireMap.locateUser();
    }
}

function resetMap() {
    if (window.quickHireMap) {
        window.quickHireMap.resetMap();
    }
}

function focusOnMarker(itemId) {
    if (window.quickHireMap) {
        window.quickHireMap.focusOnMarker(itemId);
    }
}

function hireFromMap(seekerId, seekerName) {
    if (window.quickHireMap) {
        window.quickHireMap.handleMapHire(seekerId, seekerName);
    }
}

// Initialize map with error handling
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing map...');
    
    if (typeof MAP_CONFIG !== 'undefined') {
        setTimeout(() => {
            try {
                window.quickHireMap = new QuickHireMap(MAP_CONFIG);
                console.log('QuickHireMap initialized successfully');
                
                setTimeout(() => {
                    if (window.quickHireMap) {
                        window.quickHireMap.hideAllLoadingStates();
                    }
                }, 2000);
                
            } catch (error) {
                console.error('Map initialization failed:', error);
                const overlay = document.getElementById('mapLoadingOverlay');
                if (overlay) {
                    overlay.style.display = 'none';
                }
            }
        }, 100);
    } else {
        console.error('MAP_CONFIG is not defined');
        const overlay = document.getElementById('mapLoadingOverlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }
});

// Safety timeout to hide loading states
setTimeout(() => {
    if (window.quickHireMap) {
        window.quickHireMap.hideAllLoadingStates();
    } else {
        const overlay = document.getElementById('mapLoadingOverlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }
}, 10000);