# Caltrain Tracker

A real-time Caltrain tracking application that shows upcoming train arrivals between any two Caltrain stations. The application provides a clean, user-friendly interface with train type information, arrival times, and optional sound alerts.

## Features

- Real-time train tracking between any two Caltrain stations
- Displays train type (Baby Bullet, Limited, Local)
- Shows estimated arrival times
- Direction indicators (Northbound/Southbound)
- Sound alerts for approaching trains
- Clean, modern interface with train-themed graphics
- Automatic updates every 5 seconds

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/CaltrainTracker.git
cd CaltrainTracker
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your API key:
   - Create a `.env` file in the project root directory
   - Add your Caltrain API key to the file:
   ```
   CALTRAIN_API_KEY=your_api_key_here
   ```
   - Get your API key from [511.org](https://511.org/developers)

4. Run the application:
```bash
python caltrainTracker.py
```

## Required Files

The application requires the following files:
- `caltrainTracker.py` - Main application file
- `stop_ids.csv` - Station information
- `.env` - Environment file containing your API key
- `assets/` folder containing:
  - `background.png` - Background image
  - `sprite1.png` and `sprite2.png` - Train sprites
  - `train_noises.wav` - Train sound effect

## Usage

1. Select your departure station from the "From" dropdown
2. Select your destination station from the "To" dropdown
3. Optionally enable sound alerts using the checkbox
4. The application will automatically display upcoming trains

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Caltrain for providing the API
- 511.org for the transit data 