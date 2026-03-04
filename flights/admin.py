from django.contrib import admin
from .models import (
    Airport, Airline, Aircraft, Flight, FlightSchedule,
    FlightSeatClass, FlightFare, FlightBooking, FlightPassenger
)
from travel_booking.admin import admin_site

@admin.register(Airport, site=admin_site)
class AirportAdmin(admin.ModelAdmin):
    list_display = ('name', 'iata_code', 'city', 'country', 'is_active')
    list_filter = ('country', 'is_active')
    search_fields = ('name', 'iata_code', 'city', 'country')


@admin.register(Airline, site=admin_site)
class AirlineAdmin(admin.ModelAdmin):
    list_display = ('name', 'iata_code', 'country', 'is_active')
    list_filter = ('country', 'is_active')
    search_fields = ('name', 'iata_code')


@admin.register(Aircraft, site=admin_site)
class AircraftAdmin(admin.ModelAdmin):
    list_display = ('model', 'manufacturer', 'icao_code', 'max_seating')
    search_fields = ('model', 'icao_code', 'manufacturer')


@admin.register(Flight, site=admin_site)
class FlightAdmin(admin.ModelAdmin):
    list_display = ('flight_number', 'airline', 'origin', 'destination', 'duration', 'is_active')
    list_filter = ('airline', 'is_active')
    search_fields = ('flight_number', 'airline__name', 'origin__name', 'destination__name')


@admin.register(FlightSchedule, site=admin_site)
class FlightScheduleAdmin(admin.ModelAdmin):
    list_display = ('flight', 'departure_date', 'status')
    list_filter = ('status', 'departure_date')
    search_fields = ('flight__flight_number', 'flight__airline__name')
    date_hierarchy = 'departure_date'


@admin.register(FlightSeatClass, site=admin_site)
class FlightSeatClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'display_order')
    search_fields = ('name', 'code')


@admin.register(FlightFare, site=admin_site)
class FlightFareAdmin(admin.ModelAdmin):
    list_display = ('flight_schedule', 'seat_class', 'base_fare', 'taxes', 'total_fare', 'currency')
    list_filter = ('currency',)
    search_fields = ('flight_schedule__flight__flight_number', 'flight_schedule__flight__airline__name')


@admin.register(FlightBooking, site=admin_site)
class FlightBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'flight_schedule', 'fare', 'passenger_count', 'total_amount', 'status')
    list_filter = ('status',)
    search_fields = ('user__email', 'flight_schedule__flight__flight_number', 'id')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(FlightPassenger, site=admin_site)
class FlightPassengerAdmin(admin.ModelAdmin):
    list_display = ('booking', 'first_name', 'last_name', 'passport_number', 'seat_number')
    search_fields = ('booking__user__email', 'first_name', 'last_name', 'passport_number')
