{{-- Summary Card Component
     Props:
       $title    — card heading text
       $value    — main display value
       $icon     — optional emoji/icon (default: none)
       $slot     — optional string; when 'countdown', renders countdown component below value
       $countdown — array with keys: days, hours, minutes (required when slot='countdown')
--}}
<div class="summary-card">
    @if(!empty($icon))
        <div class="summary-card-icon">{{ $icon }}</div>
    @endif
    <div class="summary-card-content">
        <div class="summary-card-title">{{ $title }}</div>
        <div class="summary-card-value">{{ $value }}</div>
        @if(!empty($slot) && $slot === 'countdown' && !empty($countdown))
            @include('components.countdown', ['countdown' => $countdown])
        @endif
    </div>
</div>
