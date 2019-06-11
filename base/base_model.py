import tensorflow as tf
from utils.logger import Logger


class BaseModel:
    def __init__(self, config):
        self.config = config
        log_object = Logger(self.config)
        self.logger = log_object.get_logger(__name__)
        # init the global step
        self.init_global_step()
        # init the epoch counter
        self.init_cur_epoch()

    # save function that saves the checkpoint in the path defined in the config file
    def save(self, sess):
        self.logger.info("Saving model...")
        self.saver.save(sess, self.config.log.checkpoint_dir, self.global_step_tensor)
        self.logger.info("Model saved")

    # load latest checkpoint from the experiment path defined in the config file
    def load(self, sess):
        latest_checkpoint = tf.train.latest_checkpoint(self.config.log.checkpoint_dir)
        if latest_checkpoint:
            self.logger.info("Loading model checkpoint {} ...\n".format(latest_checkpoint))
            self.saver.restore(sess, latest_checkpoint)
            self.logger.info("Model loaded")

    # just initialize a tensorflow variable to use it as epoch counter
    def init_cur_epoch(self):
        with tf.variable_scope("cur_epoch"):
            self.cur_epoch_tensor = tf.Variable(0, trainable=False, name="cur_epoch")
            self.increment_cur_epoch_tensor = tf.assign(
                self.cur_epoch_tensor, self.cur_epoch_tensor + 1
            )

            self.reset_cur_epoch_tensor = tf.assign(self.cur_epoch_tensor, 0)

    # just initialize a tensorflow variable to use it as global step counter
    def init_global_step(self):
        # DON'T forget to add the global step tensor to the tensorflow trainer
        with tf.variable_scope("global_step"):
            self.global_step_tensor = tf.Variable(0, trainable=False, name="global_step")

    def init_saver(self):
        # just copy the following line in your child class
        # self.saver = tf.train.Saver(max_to_keep=self.config.max_to_keep)
        raise NotImplementedError

    def build_model(self):
        raise NotImplementedError
