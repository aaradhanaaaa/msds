import asyncio
import logging
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusDeviceContext,
    ModbusServerContext,
)
from pymodbus.device import ModbusDeviceIdentification

# Enable logging to monitor server status
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)


async def run_server():
    # 1. Define register data blocks (di, co, hr, ir)
    store = ModbusDeviceContext(
        di=ModbusSequentialDataBlock(0, [1, 0, 1, 1]),       # Discrete Inputs
        co=ModbusSequentialDataBlock(0, [0, 0, 0, 0]),       # Coils
        hr=ModbusSequentialDataBlock(0, [100, 200, 300, 400]), # Holding Registers
        ir=ModbusSequentialDataBlock(0, [12, 34, 56, 78]),    # Input Registers
    )

    # 2. Setup server context for unit/device ID 1
    context = ModbusServerContext(slaves={1: store}, single=True)

    # 3. Optional server metadata
    identity = ModbusDeviceIdentification()
    identity.VendorName = "PyModbus"
    identity.ProductName = "Modbus TCP Server"
    identity.ModelName = "PyModbus Server"

    _logger.info("Starting Modbus TCP Server on 127.0.0.1:5020...")
    
    # 4. Start the async server
    await StartAsyncTcpServer(
        context=context,
        identity=identity,
        address=("127.0.0.1", 5020),
    )


if __name__ == "__main__":
    asyncio.run(run_server())