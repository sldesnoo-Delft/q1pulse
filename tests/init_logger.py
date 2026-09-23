
import logging

logging.basicConfig(filename='log.txt', filemode='w',
                    format='%(asctime)s %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)
logging.getLogger('matplotlib').setLevel(logging.INFO)