import tensorflow as tf
from utils.utils import get_args
from utils.config import process_config, get_config_from_json
from utils.factory import create
from utils.dirs import create_dirs
from utils.logger import Logger
from utils.copy_codebase import copy_codebase
import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"


def run():
    # Get the arguments
    args = get_args()
    config, _ = get_config_from_json(args.config)
    config.exp.name = args.experiment
    config = process_config(config)

    # create the experiments dirs
    create_dirs(
        [
            config.log.summary_dir,
            config.log.checkpoint_dir,
            config.log.step_generation_dir,
            config.log.log_file_dir,
            config.log.codebase_dir,
        ]
    )
    # Copy the model code and the trainer code to the experiment folder
    copy_codebase(config)
    l = Logger(config)
    logger = l.get_logger(__name__)
    # Set the random seed
    tf.random.set_random_seed(config.data_loader.random_seed)
    # Create the tensorflow session
    sess = tf.Session()
    # Create the dataloader
    data = create("data_loader." + config.data_loader.name)(config)
    # Create the model instance
    model = create("models.{}.".format(config.data_loader.image_size) + config.model.name)(config)
    # Create the summarizer Object
    summarizer = create("utils." + config.log.name)(sess, config)
    # Create the trainer
    trainer = create("trainers." + config.trainer.name)(sess, model, data, config, summarizer)
    # Load model if exists
    model.load(sess)
    # Train the model
    trainer.train()
    if config.trainer.test_at_end:
        trainer.test()
    logger.info("Experiment has ended.")


if __name__ == "__main__":
    run()
