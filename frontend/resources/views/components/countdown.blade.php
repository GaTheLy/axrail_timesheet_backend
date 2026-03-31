{{-- Countdown Component
     Props:
       $countdown — array with keys: days, hours, minutes
--}}
<div class="countdown" id="countdown-timer"
     data-days="{{ $countdown['days'] ?? 0 }}"
     data-hours="{{ $countdown['hours'] ?? 0 }}"
     data-minutes="{{ $countdown['minutes'] ?? 0 }}">
    <span class="badge badge-warning">
        <span id="countdown-days">{{ $countdown['days'] ?? 0 }}</span> Days
        <span id="countdown-hours">{{ $countdown['hours'] ?? 0 }}</span> Hours
        <span id="countdown-minutes">{{ $countdown['minutes'] ?? 0 }}</span> Minutes left
    </span>
</div>

<script>
(function () {
    var el = document.getElementById('countdown-timer');
    if (!el) return;

    var totalMinutes =
        parseInt(el.dataset.days, 10) * 1440 +
        parseInt(el.dataset.hours, 10) * 60 +
        parseInt(el.dataset.minutes, 10);

    function render() {
        if (totalMinutes <= 0) {
            totalMinutes = 0;
        }
        var d = Math.floor(totalMinutes / 1440);
        var h = Math.floor((totalMinutes % 1440) / 60);
        var m = totalMinutes % 60;

        document.getElementById('countdown-days').textContent = d;
        document.getElementById('countdown-hours').textContent = h;
        document.getElementById('countdown-minutes').textContent = m;
    }

    setInterval(function () {
        if (totalMinutes > 0) {
            totalMinutes--;
            render();
        }
    }, 60000);
})();
</script>
