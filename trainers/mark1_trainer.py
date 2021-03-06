from base.base_train import BaseTrain
from tqdm import tqdm
import numpy as np
from time import sleep
from time import time
from utils.evaluations import save_results


class Mark1_Trainer(BaseTrain):
    def __init__(self, sess, model, data, config, summarizer):
        super(Mark1_Trainer, self).__init__(sess, model, data, config, summarizer)
        # This values are added as variable becaouse they are used a lot and changing it become difficult over time.
        self.batch_size = self.config.data_loader.batch_size
        self.noise_dim = self.config.trainer.noise_dim
        self.img_dims = self.config.trainer.image_dims
        # Inititalize the train Dataset Iterator
        self.sess.run(self.data.iterator.initializer)
        # Initialize the test Dataset Iterator
        self.sess.run(self.data.test_iterator.initializer)
        if self.config.data_loader.validation:
            self.sess.run(self.data.valid_iterator.initializer)
            self.best_valid_loss = 0
            self.nb_without_improvements = 0

    def train_epoch(self):
        begin = time()
        # Attach the epoch loop to a variable
        loop = tqdm(range(self.config.data_loader.num_iter_per_epoch))
        # Define the lists for summaries and losses
        gen_losses = []
        disc_losses = []
        disc_xz_losses = []
        disc_xx_losses = []
        disc_zz_losses = []
        summaries = []
        # Get the current epoch counter
        cur_epoch = self.model.cur_epoch_tensor.eval(self.sess)
        image = self.data.image
        for _ in loop:
            loop.set_description("Epoch:{}".format(cur_epoch + 1))
            loop.refresh()  # to show immediately the update
            sleep(0.01)
            lg, ld, ldxz, ldxx, ldzz, sum_g, sum_d = self.train_step(image, cur_epoch)
            gen_losses.append(lg)
            disc_losses.append(ld)
            disc_xz_losses.append(ldxz)
            disc_xx_losses.append(ldxx)
            disc_zz_losses.append(ldzz)
            summaries.append(sum_g)
            summaries.append(sum_d)
        self.logger.info("Epoch {} terminated".format(cur_epoch))
        self.summarizer.add_tensorboard(step=cur_epoch, summaries=summaries)
        # Check for reconstruction
        if cur_epoch % self.config.log.frequency_test == 0:
            image_eval = self.sess.run(image)
            feed_dict = {self.model.image_input: image_eval, self.model.is_training: False}
            reconstruction = self.sess.run(self.model.sum_op_im, feed_dict=feed_dict)
            self.summarizer.add_tensorboard(step=cur_epoch, summaries=[reconstruction])
        # Get the means of the loss values to display
        gl_m = np.mean(gen_losses)
        dl_m = np.mean(disc_losses)
        dlxz_m = np.mean(disc_xz_losses)
        dlxx_m = np.mean(disc_xx_losses)
        dlzz_m = np.mean(disc_zz_losses)
        if self.config.trainer.allow_zz:
            self.logger.info(
                "Epoch {} | time = {} | loss gen = {:4f} |"
                "loss dis = {:4f} | loss dis xz = {:4f} | loss dis xx = {:4f} | "
                "loss dis zz = {:4f}".format(
                    cur_epoch, time() - begin, gl_m, dl_m, dlxz_m, dlxx_m, dlzz_m
                )
            )
        else:
            self.logger.info(
                "Epoch {} | time = {} | loss gen = {:4f} | "
                "loss dis = {:4f} | loss dis xz = {:4f} | loss dis xx = {:4f} | ".format(
                    cur_epoch, time() - begin, gl_m, dl_m, dlxz_m, dlxx_m
                )
            )
        # Save the model state
        # self.model.save(self.sess)

        if (
            cur_epoch + 1
        ) % self.config.trainer.frequency_eval == 0 and self.config.trainer.enable_early_stop:
            valid_loss = 0
            image_valid = self.sess.run(self.data.valid_image)

            feed_dict = {self.model.image_input: image_valid, self.model.is_training: False}
            vl = self.sess.run([self.model.rec_error_valid], feed_dict=feed_dict)
            valid_loss += vl[0]
            if self.config.log.enable_summary:
                sm = self.sess.run(self.model.sum_op_valid, feed_dict=feed_dict)
                self.summarizer.add_tensorboard(step=cur_epoch, summaries=[sm], summarizer="valid")

            self.logger.info("Validation: valid loss {:.4f}".format(valid_loss))
            if (
                valid_loss < self.best_valid_loss
                or cur_epoch == self.config.trainer.frequency_eval - 1
            ):
                self.best_valid_loss = valid_loss
                self.logger.info(
                    "Best model - valid loss = {:.4f} - saving...".format(self.best_valid_loss)
                )
                # Save the model state
                self.model.save(self.sess)
                self.nb_without_improvements = 0
            else:
                self.nb_without_improvements += self.config.trainer.frequency_eval
            if self.nb_without_improvements > self.config.trainer.patience:
                self.patience_lost = True
                self.logger.warning(
                    "Early stopping at epoch {} with weights from epoch {}".format(
                        cur_epoch, cur_epoch - self.nb_without_improvements
                    )
                )

        self.logger.warn("Testing evaluation...")
        scores = []
        inference_time = []
        true_labels = []
        # Create the scores
        test_loop = tqdm(range(self.config.data_loader.num_iter_per_test))
        for _ in test_loop:
            test_batch_begin = time()
            test_batch, test_labels = self.sess.run([self.data.test_image, self.data.test_label])
            test_loop.refresh()  # to show immediately the update
            sleep(0.01)
            feed_dict = {self.model.image_input: test_batch, self.model.is_training: False}
            scores += self.sess.run(self.model.score, feed_dict=feed_dict).tolist()
            inference_time.append(time() - test_batch_begin)
            true_labels += test_labels.tolist()
        true_labels = np.asarray(true_labels)
        inference_time = np.mean(inference_time)
        self.logger.info("Testing: Mean inference time is {:4f}".format(inference_time))
        scores = np.asarray(scores)
        scores_scaled = (scores - min(scores)) / (max(scores) - min(scores))
        step = self.sess.run(self.model.global_step_tensor)
        save_results(
            self.config.log.result_dir,
            scores_scaled,
            true_labels,
            self.config.model.name,
            self.config.data_loader.dataset_name,
            "fm",
            "paper",
            self.config.trainer.label,
            self.config.data_loader.random_seed,
            self.logger,
            step,
        )

    def train_step(self, image, cur_epoch):
        """
          implement the logic of the train step
          - run the tensorflow session
          - return any metrics you need to summarize
        """
        true_labels, generated_labels = self.generate_labels(
            self.config.trainer.soft_labels, self.config.trainer.flip_labels
        )
        # Train the discriminator
        image_eval = self.sess.run(image)
        feed_dict = {
            self.model.image_input: image_eval,
            self.model.generated_labels: generated_labels,
            self.model.true_labels: true_labels,
            self.model.is_training: True,
        }
        _, _, _, ld, ldxz, ldxx, ldzz, sm_d = self.sess.run(
            [
                self.model.train_dis_op_xz,
                self.model.train_dis_op_xx,
                self.model.train_dis_op_zz,
                self.model.loss_discriminator,
                self.model.dis_loss_xz,
                self.model.dis_loss_xx,
                self.model.dis_loss_zz,
                self.model.sum_op_dis,
            ],
            feed_dict=feed_dict,
        )

        # Train Generator
        true_labels, generated_labels = self.generate_labels(
            self.config.trainer.soft_labels, self.config.trainer.flip_labels
        )
        feed_dict = {
            self.model.image_input: image_eval,
            self.model.generated_labels: generated_labels,
            self.model.true_labels: true_labels,
            self.model.is_training: True,
        }
        _, lg, sm_g = self.sess.run(
            [self.model.train_gen_op, self.model.gen_loss_total, self.model.sum_op_gen],
            feed_dict=feed_dict,
        )

        return lg, ld, ldxz, ldxx, ldzz, sm_g, sm_d

    def generate_labels(self, soft_labels, flip_labels):

        if not soft_labels:
            true_labels = np.ones((self.config.data_loader.batch_size, 1))
            generated_labels = np.zeros((self.config.data_loader.batch_size, 1))
        else:
            generated_labels = np.zeros(
                (self.config.data_loader.batch_size, 1)
            ) + np.random.uniform(low=0.0, high=0.1, size=[self.config.data_loader.batch_size, 1])
            # flipped_idx = np.random.choice(
            #     np.arange(len(generated_labels)),
            #     size=int(self.config.trainer.noise_probability * len(generated_labels)),
            # )
            # generated_labels[flipped_idx] = 1 - generated_labels[flipped_idx]
            true_labels = np.ones((self.config.data_loader.batch_size, 1)) - np.random.uniform(
                low=0.0, high=0.1, size=[self.config.data_loader.batch_size, 1]
            )
            # flipped_idx = np.random.choice(
            #     np.arange(len(true_labels)),
            #     size=int(self.config.trainer.noise_probability * len(true_labels)),
            # )
            # true_labels[flipped_idx] = 1 - true_labels[flipped_idx]
        if flip_labels:
            return generated_labels, true_labels
        else:
            return true_labels, generated_labels
