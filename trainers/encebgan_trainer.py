from base.base_train_multi import BaseTrainMulti
from tqdm import tqdm
import numpy as np
from time import sleep
from time import time
from utils.evaluations import save_results


class EncEBGANTrainer(BaseTrainMulti):
    def __init__(self, sess, model, data, config, logger):
        super(EncEBGANTrainer, self).__init__(sess, model, data, config, logger)
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

    def train_epoch_gan(self):
        # Attach the epoch loop to a variable
        begin = time()
        # Make the loop of the epoch iterations
        loop = tqdm(range(self.config.data_loader.num_iter_per_epoch))
        gen_losses = []
        disc_losses = []
        summaries = []
        image = self.data.image
        cur_epoch = self.model.cur_epoch_tensor.eval(self.sess)
        for _ in loop:
            loop.set_description("Epoch:{}".format(cur_epoch + 1))
            loop.refresh()  # to show immediately the update
            sleep(0.01)
            lg, ld, sum_g, sum_d = self.train_step_gan(image, cur_epoch)
            gen_losses.append(lg)
            disc_losses.append(ld)
            summaries.append(sum_g)
            summaries.append(sum_d)
        self.logger.info("Epoch {} terminated".format(cur_epoch))
        self.summarizer.add_tensorboard(step=cur_epoch, summaries=summaries)

        # Check for reconstruction
        if cur_epoch % self.config.log.frequency_test == 0:
            noise = np.random.normal(
                loc=0.0, scale=1.0, size=[self.config.data_loader.test_batch, self.noise_dim]
            )
            image_eval = self.sess.run(image)
            feed_dict = {
                self.model.image_input: image_eval,
                self.model.noise_tensor: noise,
                self.model.is_training_gen: False,
                self.model.is_training_dis: False,
            }
            reconstruction = self.sess.run(self.model.sum_op_im_1, feed_dict=feed_dict)
            self.summarizer.add_tensorboard(step=cur_epoch, summaries=[reconstruction])
        gen_m = np.mean(gen_losses)
        dis_m = np.mean(disc_losses)
        self.logger.info(
            "Epoch: {} | time = {} s | loss gen= {:4f} | loss dis = {:4f} ".format(
                cur_epoch, time() - begin, gen_m, dis_m
            )
        )
        self.model.save(self.sess)

    def train_epoch_enc(self):
        # Attach the epoch loop to a variable
        begin = time()
        # Make the loop of the epoch iterations
        loop = tqdm(range(self.config.data_loader.num_iter_per_epoch))
        enc_losses = []
        summaries = []
        image = self.data.image
        cur_epoch = self.model.cur_epoch_tensor.eval(self.sess)
        for _ in loop:
            loop.set_description("Epoch:{}".format(cur_epoch + 1))
            loop.refresh()  # to show immediately the update
            sleep(0.01)
            le, sum_e = self.train_step_enc(image, cur_epoch)
            enc_losses.append(le)
            summaries.append(sum_e)
        self.logger.info("Epoch {} terminated".format(cur_epoch))
        self.summarizer.add_tensorboard(step=cur_epoch, summaries=summaries, summarizer="valid")
        # Check for reconstruction
        if cur_epoch % self.config.log.frequency_test == 0:
            noise = np.random.normal(
                loc=0.0, scale=1.0, size=[self.config.data_loader.test_batch, self.noise_dim]
            )
            image_eval = self.sess.run(image)
            feed_dict = {
                self.model.image_input: image_eval,
                self.model.noise_tensor: noise,
                self.model.is_training_gen: False,
                self.model.is_training_enc: False,
                self.model.is_training_dis: False,
            }
            reconstruction = self.sess.run(self.model.sum_op_im_2, feed_dict=feed_dict)
            self.summarizer.add_tensorboard(
                step=cur_epoch, summaries=[reconstruction], summarizer="valid"
            )
        enc_m = np.mean(enc_losses)
        self.logger.info(
            "Epoch: {} | time = {} s | loss enc= {:4f}  ".format(cur_epoch, time() - begin, enc_m)
        )
        self.model.save(self.sess)

    def train_step_gan(self, image, cur_epoch):
        ld_t, lg_t, sm_g, sm_d = [], [], None, None
        image_eval = self.sess.run(image)
        if self.config.trainer.mode == "standard":
            disc_iters = 1
        else:
            disc_iters = self.config.trainer.critic_iters
        for _ in range(disc_iters):
            noise = np.random.normal(loc=0.0, scale=1.0, size=[self.batch_size, self.noise_dim])
            feed_dict = {
                self.model.image_input: image_eval,
                self.model.noise_tensor: noise,
                self.model.is_training_gen: True,
                self.model.is_training_dis: True,
                self.model.is_training_enc: False,
            }
            _, ld, sm_d = self.sess.run(
                [self.model.train_dis_op, self.model.loss_discriminator, self.model.sum_op_dis],
                feed_dict=feed_dict,
            )
            ld_t.append(ld)

        if self.config.trainer.mode == "standard":
            gen_iters = 1
        else:
            gen_iters = 3
        for _ in range(gen_iters):
            image_eval = self.sess.run(image)
            noise = np.random.normal(loc=0.0, scale=1.0, size=[self.batch_size, self.noise_dim])
            feed_dict = {
                self.model.image_input: image_eval,
                self.model.noise_tensor: noise,
                self.model.is_training_gen: True,
                self.model.is_training_dis: True,
                self.model.is_training_enc: False,
            }
            _, lg, sm_g = self.sess.run(
                [self.model.train_gen_op, self.model.loss_generator, self.model.sum_op_gen],
                feed_dict=feed_dict,
            )
            lg_t.append(lg)

        return np.mean(lg_t), np.mean(ld_t), sm_g, sm_d

    def train_step_enc(self, image, cur_epoch):
        image_eval = self.sess.run(image)
        noise = np.random.normal(loc=0.0, scale=1.0, size=[self.batch_size, self.noise_dim])
        feed_dict = {
            self.model.image_input: image_eval,
            self.model.noise_tensor: noise,
            self.model.is_training_gen: False,
            self.model.is_training_dis: False,
            self.model.is_training_enc: True,
        }
        _, le, sm_e = self.sess.run(
            [self.model.train_enc_op, self.model.loss_encoder, self.model.sum_op_enc],
            feed_dict=feed_dict,
        )
        return le, sm_e

    def test_epoch(self):
        self.logger.warn("Testing evaluation...")
        scores_im1 = []
        scores_im2 = []
        scores_z1 = []
        scores_z2 = []
        scores_comb = []
        scores_comb2 = []
        inference_time = []
        true_labels = []
        summaries = []
        # Create the scores
        test_loop = tqdm(range(self.config.data_loader.num_iter_per_test))
        cur_epoch = self.model.cur_epoch_tensor.eval(self.sess)
        for _ in test_loop:
            test_batch_begin = time()
            test_batch, test_labels = self.sess.run([self.data.test_image, self.data.test_label])
            test_loop.refresh()  # to show immediately the update
            sleep(0.01)
            noise = np.random.normal(
                loc=0.0, scale=1.0, size=[self.config.data_loader.test_batch, self.noise_dim]
            )
            feed_dict = {
                self.model.image_input: test_batch,
                self.model.noise_tensor: noise,
                self.model.is_training_gen: False,
                self.model.is_training_dis: False,
                self.model.is_training_enc: False,
            }
            scores_im1 += self.sess.run(self.model.img_score_l1, feed_dict=feed_dict).tolist()
            scores_im2 += self.sess.run(self.model.img_score_l2, feed_dict=feed_dict).tolist()
            scores_z1 += self.sess.run(self.model.z_score_l1, feed_dict=feed_dict).tolist()
            scores_z2 += self.sess.run(self.model.z_score_l2, feed_dict=feed_dict).tolist()
            scores_comb += self.sess.run(self.model.score_comb, feed_dict=feed_dict).tolist()
            scores_comb2 += self.sess.run(self.model.score_comb_2, feed_dict=feed_dict).tolist()
            summaries += self.sess.run([self.model.sum_op_im_test], feed_dict=feed_dict)
            inference_time.append(time() - test_batch_begin)
            true_labels += test_labels.tolist()
        self.summarizer.add_tensorboard(step=cur_epoch, summaries=summaries, summarizer="test")
        scores_im1 = np.asarray(scores_im1)
        scores_im2 = np.asarray(scores_im2)
        scores_z1 = np.asarray(scores_z1)
        scores_z2 = np.asarray(scores_z2)
        scores_comb = np.asarray(scores_comb)
        scores_comb2 = np.asarray(scores_comb2)
        true_labels = np.asarray(true_labels)
        inference_time = np.mean(inference_time)
        self.logger.info("Testing: Mean inference time is {:4f}".format(inference_time))
        step = self.sess.run(self.model.global_step_tensor)
        percentiles = np.asarray(self.config.trainer.percentiles)
        save_results(
            self.config.log.result_dir,
            scores_im1,
            true_labels,
            self.config.model.name,
            self.config.data_loader.dataset_name,
            "im1",
            "paper",
            self.config.trainer.label,
            self.config.data_loader.random_seed,
            self.logger,
            step,
            percentile=percentiles,
        )
        save_results(
            self.config.log.result_dir,
            scores_im2,
            true_labels,
            self.config.model.name,
            self.config.data_loader.dataset_name,
            "im2",
            "paper",
            self.config.trainer.label,
            self.config.data_loader.random_seed,
            self.logger,
            step,
            percentile=percentiles,
        )
        save_results(
            self.config.log.result_dir,
            scores_z1,
            true_labels,
            self.config.model.name,
            self.config.data_loader.dataset_name,
            "z1",
            "paper",
            self.config.trainer.label,
            self.config.data_loader.random_seed,
            self.logger,
            step,
            percentile=percentiles,
        )
        save_results(
            self.config.log.result_dir,
            scores_z2,
            true_labels,
            self.config.model.name,
            self.config.data_loader.dataset_name,
            "z2",
            "paper",
            self.config.trainer.label,
            self.config.data_loader.random_seed,
            self.logger,
            step,
            percentile=percentiles,
        )
        save_results(
            self.config.log.result_dir,
            scores_comb,
            true_labels,
            self.config.model.name,
            self.config.data_loader.dataset_name,
            "comb",
            "paper",
            self.config.trainer.label,
            self.config.data_loader.random_seed,
            self.logger,
            step,
            percentile=percentiles,
        )
        save_results(
            self.config.log.result_dir,
            scores_comb2,
            true_labels,
            self.config.model.name,
            self.config.data_loader.dataset_name,
            "comb_2",
            "paper",
            self.config.trainer.label,
            self.config.data_loader.random_seed,
            self.logger,
            step,
            percentile=percentiles,
        )
