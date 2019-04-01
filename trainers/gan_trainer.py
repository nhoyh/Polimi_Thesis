from base.base_train import BaseTrain
from tqdm import tqdm
import numpy as np
import tensorflow as tf
from tensorflow.keras import backend as K
from time import sleep
# tf.enable_eager_execution()
import time


class GANTrainer(BaseTrain):
    def __init__(self, sess, model, data, config, logger):
        super(GANTrainer, self).__init__(sess, model, data, config, logger)

    def train_epoch(self):
        """
       implement the logic of epoch:
       -loop on the number of iterations in the config and call the train step
       -add any summaries you want using the summary
        """
        # Attach the epoch loop to a variable
        loop = tqdm(range(self.config.num_iter_per_epoch))
        # Define the lists for summaries and losses
        gen_losses = []
        disc_losses = []
        summaries = []
        
        # Get the current epoch counter
        cur_epoch = self.model.cur_epoch_tensor.eval(self.sess)
        self.sess.run(self.data.iterator.initializer)
        for epoch in loop:
            loop.set_description("Epoch:{}".format(cur_epoch))
            loop.refresh()  # to show immediately the update
            sleep(0.01)
            # Calculate the losses and obtain the summaries to write
            gen_loss, disc_loss, summary = self.train_step(
                self.data.next_element,
                cur_epoch=cur_epoch
            )
            gen_losses.append(gen_loss)
            disc_losses.append(disc_loss)
            summaries.append(summary)
        # write the summaries
        self.logger.summarize(cur_epoch, summaries=summaries)
        # Compute the means of the losses
        gen_loss_m = np.mean(gen_losses)
        disc_loss_m = np.mean(disc_losses)
        # Generate images between epochs to evaluate
        rand_noise = self.sess.run(self.model.random_vector_for_generation)
        feed_dict = {self.model.noise_tensor: rand_noise,
                     K.learning_phase(): 0}
        generator_predictions = self.sess.run(
            [self.model.progress_images], feed_dict=feed_dict
        )
        self.save_generated_images(generator_predictions, cur_epoch)

        if cur_epoch % self.config.show_steps == 0 or cur_epoch == 1:
            print(
                "Epoch {} --\nGenerator Loss: {}\nDiscriminator Loss: {}\n".format(
                    cur_epoch + 1, gen_loss_m, disc_loss_m, 
                )
            )

        self.model.save(self.sess)

    def train_step(self, image, cur_epoch):

        # Generate noise from uniform  distribution between -1 and 1
        # New Noise Generation
        # noise = np.random.uniform(-1., 1.,size=[self.config.batch_size, self.config.noise_dim])
        noise_probability = self.config.noise_probability
        sigma = max(0.75 * (10. - cur_epoch) / (10), 0.05)
        noise = np.random.normal(loc=0.0, scale=1.0, size=[self.config.batch_size, self.config.noise_dim])
        true_labels = np.zeros((self.config.batch_size,1)) + np.random.uniform(low=0.0, high=0.1, size=[self.config.batch_size, 1])
        flipped_idx = np.random.choice(np.arange(len(true_labels)), size= int(noise_probability * len(true_labels)))
        true_labels[flipped_idx] = 1 - true_labels[flipped_idx]
        generated_labels = np.ones((self.config.batch_size,1)) - np.random.uniform(low=0.0, high=0.1, size=[self.config.batch_size, 1])
        flipped_idx = np.random.choice(np.arange(len(generated_labels)), size=int(noise_probability * len(generated_labels)))
        generated_labels[flipped_idx] =  1 - generated_labels[flipped_idx]
        # Instance noise additions
        if self.config.include_noise:
            # If we want to add this is will add the noises
            real_noise = np.random.normal(scale=sigma, size=[self.config.batch_size] + self.config.image_dims)
            fake_noise = np.random.normal(scale=sigma, size=[self.config.batch_size] + self.config.image_dims)
        else:
            # Otherwise we are just going to add zeros which will not break anything
            real_noise = np.zeros(([self.config.batch_size] + self.config.image_dims))
            fake_noise = np.zeros(([self.config.batch_size] + self.config.image_dims))
        # Evaluation of the image
        image_eval = self.sess.run(image)
        # Construct the Feed Dictionary
        # Train the Discriminator on both real and fake images
        _ = self.sess.run([self.model.train_disc],
            feed_dict={
                self.model.noise_tensor: noise,
                self.model.image_input: image_eval,
                self.model.real_noise: real_noise,
                self.model.fake_noise: fake_noise,
                self.model.true_labels: true_labels,
                self.model.generated_labels: generated_labels,
                K.learning_phase(): 1
            }
        )
        # Train the Generator and get the summaries
        # Re create the noise for the generator
        noise = np.random.normal(loc=0.0, scale=1.0, size=[self.config.batch_size, self.config.noise_dim])
        _ = self.sess.run(
            [self.model.train_gen],
            feed_dict={
                self.model.noise_tensor: noise,
                self.model.image_input: image_eval,
                self.model.real_noise: real_noise,
                self.model.fake_noise: fake_noise,
                self.model.true_labels: true_labels,
                self.model.generated_labels: generated_labels,
                K.learning_phase(): 1
            }
            )

        # Calculate the losses
        gen_loss, disc_loss, summary = self.sess.run(
            [self.model.gen_loss,
             self.model.total_disc_loss,
             self.model.summary],
            feed_dict={
                self.model.noise_tensor: noise,
                self.model.image_input: image_eval,
                self.model.real_noise: real_noise,
                self.model.fake_noise: fake_noise,
                self.model.true_labels: true_labels,
                self.model.generated_labels: generated_labels,
                K.learning_phase(): 1
            }
        )

        return gen_loss, disc_loss, summary
