{{-- Entry Modal — Add / Edit timesheet entry --}}
<div id="entry-modal-overlay" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="entry-modal-title">
    <div id="entry-modal" class="modal">
        {{-- Header --}}
        <div class="modal-header">
            <h3 id="entry-modal-title">Add New Entry</h3>
            <button type="button" class="modal-close" id="btn-close-entry-modal" aria-label="Close modal">&times;</button>
        </div>

        {{-- Body --}}
        <div class="modal-body">
            {{-- Error display --}}
            <div id="entry-modal-error" class="alert alert-error" style="display: none;" role="alert"></div>

            {{-- Hidden entry ID for edit mode --}}
            <input type="hidden" id="entry-id" value="">

            <div class="form-group">
                <label for="entry-project-code">Project Code <span aria-hidden="true">*</span></label>
                <select id="entry-project-code" required aria-required="true">
                    <option value="">Select a project…</option>
                </select>
            </div>

            <div class="form-group">
                <label for="entry-description">Description</label>
                <input type="text" id="entry-description" placeholder="Brief description of work performed">
            </div>

            <div class="form-group">
                <label for="entry-date">Date <span aria-hidden="true">*</span></label>
                <input type="date" id="entry-date" required aria-required="true">
            </div>

            <div class="form-group">
                <label for="entry-hours">Charged Hours <span aria-hidden="true">*</span></label>
                <input type="number" id="entry-hours" min="0" step="0.01" placeholder="0.00" required aria-required="true">
            </div>
        </div>

        {{-- Footer --}}
        <div class="modal-footer">
            <button type="button" class="btn btn-secondary" id="btn-cancel-entry">Cancel</button>
            <button type="button" class="btn btn-primary" id="btn-save-entry" disabled>Save Changes</button>
        </div>
    </div>
</div>
