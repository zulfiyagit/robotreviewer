"""
RobotReviewer ML worker

called by `celery -A ml_worker worker --loglevel=info`

"""


# Authors:  Iain Marshall <mail@ijmarshall.com>
#           Joel Kuiper <me@joelkuiper.com>
#           Byron Wallace <byron@ccs.neu.edu>


from celery import Celery, current_task
import logging, os



log.info("RobotReviewer machine learning tasks starting")

DEBUG_MODE = str2bool(os.environ.get("DEBUG", "true"))
LOCAL_PATH = "robotreviewer/uploads"
LOG_LEVEL = (logging.DEBUG if DEBUG_MODE else logging.INFO)
# determined empirically by Edward; covers 90% of abstracts
# (crudely and unscientifically adjusted for grobid)
NUM_WORDS_IN_ABSTRACT = 450


logging.basicConfig(level=LOG_LEVEL, format='[%(levelname)s] %(name)s %(asctime)s: %(message)s')
log = logging.getLogger(__name__)


from robotreviewer.textprocessing.pdfreader import PdfReader
pdf_reader = PdfReader() # launch Grobid process before anything else


from robotreviewer.textprocessing.tokenizer import nlp

''' robots! '''
# from robotreviewer.robots.bias_robot import BiasRobot
from robotreviewer.robots.rationale_robot import BiasRobot
from robotreviewer.robots.pico_robot import PICORobot
from robotreviewer.robots.rct_robot import RCTRobot
from robotreviewer.robots.pubmed_robot import PubmedRobot
# from robotreviewer.robots.mendeley_robot import MendeleyRobot
# from robotreviewer.robots.ictrp_robot import ICTRPRobot
from robotreviewer.robots import pico_viz_robot
from robotreviewer.robots.pico_viz_robot import PICOVizRobot
from robotreviewer.robots.sample_size_robot import SampleSizeBot

from robotreviewer.data_structures import MultiDict

from robotreviewer import config
import robotreviewer


######
## default annotation pipeline defined here
######
log.info("Loading the robots...")
bots = {"bias_bot": BiasRobot(top_k=3),
        "pico_bot": PICORobot(),
        "pubmed_bot": PubmedRobot(),
        # "ictrp_bot": ICTRPRobot(),
        "rct_bot": RCTRobot(),
        "pico_viz_bot": PICOVizRobot(),
        "sample_size_bot":SampleSizeBot()}
        # "mendeley_bot": MendeleyRobot()}

log.info("Robots loaded successfully! Ready...")

# lastly wait until Grobid is connected
pdf_reader.connect()

# start up Celery service
app = Celery('ml_worker', backend='ampq://', broker='pyampq://')

#####
## connect to and set up database
#####
rr_sql_conn = sqlite3.connect(robotreviewer.get_data('uploaded_pdfs/uploaded_pdfs.sqlite'), detect_types=sqlite3.PARSE_DECLTYPES)


c = rr_sql_conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS doc_queue (id INTEGER PRIMARY KEY, report_uuid TEXT, pdf_uuid TEXT, pdf_file BLOB, timestamp TIMESTAMP)')

c.execute('CREATE TABLE IF NOT EXISTS article(id INTEGER PRIMARY KEY, report_uuid TEXT, pdf_uuid TEXT, pdf_hash TEXT, pdf_file BLOB, annotations TEXT, timestamp TIMESTAMP, dont_delete INTEGER)')
c.close()
rr_sql_conn.commit()

@app.task
def annotate(report_uuid):
    """
    takes a report uuid as input
    searches for pdfs using that id,
    then saves annotations in database
    """
    pdf_uuids = []

    c = rr.sql_conn.cursor()

    pdf_blobs = []

    for pdf_uuid, pdf_hash, pdf_file, timestamp, dont_delete in c.execute("SELECT pdf_uuid, pdf_hash, pdf_file, timestamp FROM doc_queue WHERE report_uuid=?", (report_uuid)):
        data = MultiDict()
        articles = pdf_reader.convert_batch(blobs)
        parsed_articles = []
        for doc in nlp.pipe((d.get('text', u'') for d in articles), batch_size=1, n_threads=config.SPACY_THREADS, tag=True, parse=True, entity=False):
        parsed_articles.append(doc)

        # adjust the tag, parse, and entity values if these are needed later
        for article, parsed_text in zip(articles, parsed_articles):
            article._spacy['parsed_text'] = parsed_text

        for filename, blob, data in zip(filenames, blobs, articles):
            pdf_hash = hashlib.md5(blob).hexdigest()
            pdf_uuid = rand_id()
            pdf_uuids.append(pdf_uuid)
            data = annotate(data, bot_names=["pubmed_bot", "bias_bot", "pico_bot", "rct_bot", "pico_viz_bot", "sample_size_bot"])
            data.gold['pdf_uuid'] = pdf_uuid
            data.gold['filename'] = filename
            c.execute("INSERT INTO article (report_uuid, pdf_uuid, pdf_hash, pdf_file, annotations, timestamp, dont_delete) VALUES(?, ?, ?, ?, ?, ?, ?)", (report_uuid, pdf_uuid, pdf_hash, sqlite3.Binary(blob), data.to_json(), datetime.now(), config.DONT_DELETE))
            rr_sql_conn.commit()
            c.close()






