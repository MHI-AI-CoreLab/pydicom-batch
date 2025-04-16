# PYDICOM Batch Export

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.12.1-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

</div>

This project provides Python-based batch image export scripts for PACS servers compliant with the DICOM protocol. It enables efficient extraction and management of medical images, making it ideal for data science projects and AI research that require large-scale medical imaging datasets.

## 🚀� Acknowledgment

This project is based on the excellent work of [pydicom-batch](https://github.com/therlaup/pydicom-batch) by [@therlaup](https://github.com/therlaup). The original project provided the foundation and inspiration for this implementation. We've adapted and restructured the codebase while maintaining the core functionality and robustness of the original work.

## 🚀 Features

- DICOM C-FIND queries for discovering available images
- DICOM C-MOVE operations for image retrieval
- Configurable batch operations via YAML files
- CSV-based batch request management
- Support for data anonymization
- Flexible directory structure for exported files

## 🛠️ Prerequisites

- Python 3.12.1
- Access to a DICOM-compliant PACS server
- Network connectivity to the PACS server
- Proper firewall configuration for DICOM communication

## ⚙️ Installation

1. Create and activate a Conda environment:
```bash
conda create --name pydicom-batch python=3.12.1
conda activate pydicom-batch
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

## 🔧 Configuration

### Port Configuration

If not running in a container with port forwarding, configure your firewall to allow communication with the PACS server (example for port 4000).:

```bash
# Add TCP port
sudo firewall-cmd --add-port=4000/tcp --permanent

# Add UDP port (if needed)
sudo firewall-cmd --add-port=4000/udp --permanent

# Reload firewall
sudo firewall-cmd --reload

# Verify ports
sudo firewall-cmd --list-ports
```

### DICOM Configuration

1. Copy the template configuration:
```bash
cp config/dicom-template.yml.example config/dicom.yml
```

2. Edit `config/dicom.yml` with your specific PACS server settings:
   - PACS server hostname/IP
   - Port numbers
   - Application Entity Titles (AET)
   - Query parameters

## 🚀 Usage

Run the main script:
```bash
python main.py
```

## 📁 Project Structure

- `config/` - Configuration files and templates
- `data/` - Storage for exported DICOM files and databases
- `scu.py` - Service Class User implementation
- `scp.py` - Service Class Provider implementation
- `main.py` - Main execution script
- `common.py` - Shared utilities and functions

## 🔍 Technical Details

The project is built on top of:
- [Pydicom](https://github.com/pydicom/pydicom) - DICOM file handling
- [Pynetdicom](https://github.com/pydicom/pynetdicom) - DICOM networking protocol

## 📝 Important DICOM Concepts

DICOM communication involves:
- **SCU (Service Class User)** - Generates requests
- **SCP (Service Class Provider)** - Responds to requests
- **AE (Application Entity)** - Unique identifiers for DICOM nodes
- **Operations**: C-FIND (query), C-MOVE (transfer), C-STORE (storage)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

