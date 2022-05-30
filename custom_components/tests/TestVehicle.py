import unittest

from datetime import date

from kia_uvo import Vehicle
from kia_uvo import Token


class TestVehicle(unittest.TestCase):

    vehicle = Vehicle(
        None,
        None,
        Token(
            {
                "vehicle_name": "Foo",
                "vehicle_model": "Model",
                "vehicle_id": "1",
                "vehicle_registration_date": "2022-01-01",
            }
        ),
        None,
        None,
        None,
        None,
    )

    def test_set_average_electric_consumption_today(self):
        today = date.today().strftime("%Y%m%d")

        drive_history = {
            "drivingInfoDetail": [
                {"drivingDate": "20220413", "totalPwrCsp": 1000, "calculativeOdo": 100},
                {"drivingDate": today, "totalPwrCsp": 23400, "calculativeOdo": 100},
            ]
        }

        self.vehicle.set_average_electric_consumption_today(drive_history)

        self.assertEqual(
            self.vehicle.vehicle_data["averageElectricConsumptionToday"], 23.4
        )

    def test_set_average_electric_consumption_today_with_empty_history(self):
        drive_history = {"drivingInfoDetail": []}

        self.vehicle.set_average_electric_consumption_today({"drivingInfoDetail": []})

        self.assertEqual(
            self.vehicle.vehicle_data["averageElectricConsumptionToday"], 0.0
        )

    def test_set_average_electric_consumption_today_with_no_data_for_today(self):
        drive_history = {
            "drivingInfoDetail": [
                {"drivingDate": "20220413", "totalPwrCsp": 1000, "calculativeOdo": 100},
                {
                    "drivingDate": "20220412",
                    "totalPwrCsp": 23400,
                    "calculativeOdo": 100,
                },
            ]
        }

        self.vehicle.set_average_electric_consumption_today(drive_history)

        self.assertEqual(
            self.vehicle.vehicle_data["averageElectricConsumptionToday"], 0.0
        )
