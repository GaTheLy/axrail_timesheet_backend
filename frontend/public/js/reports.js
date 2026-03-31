/**
 * TimeFlow — Reports page interactions
 *
 * Provides: search filtering, status filtering, pagination,
 * period dropdown navigation, PDF export, and sidebar toggle fallback.
 */
(function () {
    'use strict';

    var PAGE_SIZE = 10;
    var currentPage = 1;

    // ── Element references ──────────────────────────────────────────────

    var searchInput;
    var periodSelect;
    var statusSelect;
    var completenessFilter;
    var reportTable;
    var exportBtn;
    var paginationInfo;
    var paginationControls;
    var allRows = [];

    // ── Page detection ──────────────────────────────────────────────────

    var path = window.location.pathname;
    var isProjectSummary = path.indexOf('/reports/project-summary') !== -1;
    var isSubmissionSummary = path.indexOf('/reports/submission-summary') !== -1;
    var itemLabel = isProjectSummary ? 'projects' : 'submissions';

    // ── Helpers ─────────────────────────────────────────────────────────

    function getExportUrl() {
        if (isProjectSummary) return '/reports/project-summary/export';
        if (isSubmissionSummary) return '/reports/submission-summary/export';
        return null;
    }

    /**
     * Return the set of visible (filtered) rows based on search text
     * and status dropdown value.
     */
    function getFilteredRows() {
        var searchText = (searchInput ? searchInput.value : '').toLowerCase().trim();
        var statusValue = (statusSelect ? statusSelect.value : '').toLowerCase().trim();
        var completenessValue = (completenessFilter ? completenessFilter.value : 'all').toLowerCase().trim();
        var filtered = [];

        for (var i = 0; i < allRows.length; i++) {
            var row = allRows[i];
            var searchable = (row.getAttribute('data-searchable') || '');
            var rowStatus = (row.getAttribute('data-status') || '');

            var matchesSearch = !searchText || searchable.indexOf(searchText) !== -1;
            var matchesStatus = !statusValue || rowStatus === statusValue;

            // Completeness filter: complete = totalHours >= 40, incomplete = totalHours < 40
            var matchesCompleteness = true;
            if (completenessValue !== 'all') {
                var totalHours = parseFloat(row.getAttribute('data-total-hours') || '0');
                if (completenessValue === 'complete') {
                    matchesCompleteness = totalHours >= 40;
                } else if (completenessValue === 'incomplete') {
                    matchesCompleteness = totalHours < 40;
                }
            }

            if (matchesSearch && matchesStatus && matchesCompleteness) {
                filtered.push(row);
            }
        }

        return filtered;
    }

    // ── Filtering ───────────────────────────────────────────────────────

    function applyFilters() {
        var filtered = getFilteredRows();

        // Hide all rows first
        for (var i = 0; i < allRows.length; i++) {
            allRows[i].style.display = 'none';
            allRows[i]._filtered = false;
        }

        // Mark filtered rows
        for (var j = 0; j < filtered.length; j++) {
            filtered[j]._filtered = true;
        }

        // Reset to page 1 and paginate
        currentPage = 1;
        paginate(filtered);
    }

    // ── Pagination ──────────────────────────────────────────────────────

    function paginate(filtered) {
        if (!filtered) {
            filtered = getFilteredRows();
        }

        var totalItems = filtered.length;
        var totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));

        if (currentPage > totalPages) currentPage = totalPages;
        if (currentPage < 1) currentPage = 1;

        var startIdx = (currentPage - 1) * PAGE_SIZE;
        var endIdx = Math.min(startIdx + PAGE_SIZE, totalItems);

        // Hide all rows, then show only current page rows
        for (var i = 0; i < allRows.length; i++) {
            allRows[i].style.display = 'none';
        }
        for (var j = startIdx; j < endIdx; j++) {
            filtered[j].style.display = '';
        }

        // Update pagination info text
        var showingCount = endIdx - startIdx;
        if (paginationInfo) {
            if (totalItems === 0) {
                paginationInfo.textContent = 'Showing 0 of 0 ' + itemLabel;
            } else {
                paginationInfo.textContent = 'Showing ' + showingCount + ' of ' + totalItems + ' ' + itemLabel;
            }
        }

        // Render page controls
        renderPageControls(totalPages, totalItems);
    }

    function renderPageControls(totalPages, totalItems) {
        if (!paginationControls) return;
        paginationControls.innerHTML = '';

        if (totalPages <= 1) return;

        // Previous button
        var prevBtn = document.createElement('button');
        prevBtn.textContent = 'Previous';
        prevBtn.className = 'pagination-btn';
        prevBtn.disabled = currentPage === 1;
        prevBtn.addEventListener('click', function () {
            if (currentPage > 1) {
                currentPage--;
                paginate();
            }
        });
        paginationControls.appendChild(prevBtn);

        // Page number buttons
        for (var p = 1; p <= totalPages; p++) {
            var pageBtn = document.createElement('button');
            pageBtn.textContent = p;
            pageBtn.className = 'pagination-btn' + (p === currentPage ? ' active' : '');
            pageBtn.setAttribute('data-page', p);
            pageBtn.addEventListener('click', function () {
                currentPage = parseInt(this.getAttribute('data-page'), 10);
                paginate();
            });
            paginationControls.appendChild(pageBtn);
        }

        // Next button
        var nextBtn = document.createElement('button');
        nextBtn.textContent = 'Next';
        nextBtn.className = 'pagination-btn';
        nextBtn.disabled = currentPage === totalPages;
        nextBtn.addEventListener('click', function () {
            if (currentPage < totalPages) {
                currentPage++;
                paginate();
            }
        });
        paginationControls.appendChild(nextBtn);
    }

    // ── Period dropdown ─────────────────────────────────────────────────

    function handlePeriodChange() {
        if (!periodSelect) return;
        var value = periodSelect.value;
        if (value) {
            window.location.href = window.location.pathname + '?periodId=' + encodeURIComponent(value);
        }
    }

    // ── PDF Export ──────────────────────────────────────────────────────

    function showExportError(msg) {
        // Remove any existing export error
        var existing = document.getElementById('export-error');
        if (existing) existing.remove();

        // Create inline error notification
        var errorDiv = document.createElement('div');
        errorDiv.id = 'export-error';
        errorDiv.className = 'alert alert-error';
        errorDiv.style.marginTop = '1rem';
        errorDiv.textContent = msg;

        // Insert after the page header
        var header = document.querySelector('.page-header');
        if (header && header.nextSibling) {
            header.parentNode.insertBefore(errorDiv, header.nextSibling);
        }

        // Auto-remove after 8 seconds
        setTimeout(function () {
            if (errorDiv.parentNode) errorDiv.remove();
        }, 8000);
    }

    function handleExportPdf() {
        var exportUrl = getExportUrl();
        if (!exportUrl || !exportBtn) return;

        var periodId = periodSelect ? periodSelect.value : '';
        if (!periodId) {
            if (window.showNotification) {
                window.showNotification('Please select a period first.', 'error');
            } else {
                alert('Please select a period first.');
            }
            return;
        }

        // Disable button and show loading state
        var originalText = exportBtn.textContent;
        exportBtn.disabled = true;
        exportBtn.textContent = 'Exporting...';

        var url = exportUrl + '?periodId=' + encodeURIComponent(periodId);

        fetch(url, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        })
        .then(function (response) {
            return response.json();
        })
        .then(function (data) {
            if (data.success && data.url) {
                window.open(data.url, '_blank');
            } else {
                var errorMsg = (data.error) || 'Failed to generate PDF. Please try again.';
                showExportError(errorMsg);
            }
        })
        .catch(function (err) {
            showExportError('An error occurred while exporting. Please try again.');
        })
        .finally(function () {
            exportBtn.disabled = false;
            exportBtn.textContent = '';
            // Re-add the SVG icon and text
            exportBtn.innerHTML =
                '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
                '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>' +
                '<polyline points="7 10 12 15 17 10"></polyline>' +
                '<line x1="12" y1="15" x2="12" y2="3"></line>' +
                '</svg> Export PDF';
        });
    }

    // ── Sidebar toggle fallback ─────────────────────────────────────────
    // NOTE: Removed duplicate event listener that was causing double-toggle issue.
    // The inline onclick on .nav-group-toggle buttons already handles the toggle.
    // Adding another listener here caused the class to be toggled twice (on then off).

    // ── Initialization ──────────────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', function () {
        searchInput = document.getElementById('search-input');
        periodSelect = document.getElementById('period-select');
        statusSelect = document.getElementById('status-select');
        completenessFilter = document.getElementById('completeness-filter');
        reportTable = document.getElementById('report-table');
        exportBtn = document.getElementById('export-pdf-btn');
        paginationInfo = document.querySelector('.pagination-info');
        paginationControls = document.getElementById('pagination-controls');

        // Collect all data rows (exclude tfoot rows)
        if (reportTable) {
            var tbody = reportTable.querySelector('tbody');
            if (tbody) {
                allRows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
            }
        }

        // Bind search input
        if (searchInput) {
            searchInput.addEventListener('keyup', function () {
                applyFilters();
            });
        }

        // Bind status dropdown
        if (statusSelect) {
            statusSelect.addEventListener('change', function () {
                applyFilters();
            });
        }

        // Bind completeness filter dropdown
        if (completenessFilter) {
            completenessFilter.addEventListener('change', function () {
                applyFilters();
            });
        } else {
            // Graceful degradation: if filter element not found, default to showing all submissions
            completenessFilter = null;
        }

        // Bind period dropdown
        if (periodSelect) {
            periodSelect.addEventListener('change', handlePeriodChange);
        }

        // Bind export button
        if (exportBtn) {
            exportBtn.addEventListener('click', handleExportPdf);
        }

        // Run initial pagination on all rows
        if (allRows.length > 0) {
            paginate();
        }
    });

})();
