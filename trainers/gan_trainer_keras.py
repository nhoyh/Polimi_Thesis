from base.base_train_keras import BaseTrainKeras

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
from time import sleep

class GANTrainerKeras(BaseTrainKeras):
    def __init__(self,sess, model, data, config):
        super(GANTrainerKeras, self).__init__(sess,model, data, config)

    def train(self):
        """
        implement the logic of epoch:
        -loop on the number of iterations in the config and call the train step
        -add any summaries you want using the summary
        """
        loop = tqdm(range(self.config.num_epochs))
        self.sess.run(self.data.iterator.initializer)
        for epoch in loop:
            loop.set_description("Epoch:{}".format(epoch))
            loop.refresh()  # to show immediately the update
            sleep(0.01)
        # Get the current epoch counter
            noise_probability = self.config.noise_probability
            noise = np.random.normal(loc=0.0, scale=1.0, size=[self.config.batch_size, self.config.noise_dim])
            # Soft Label Generation
            true_labels = np.zeros((self.config.batch_size, 1)) + np.random.uniform(
                low=0.0, high=0.1,size=[self.config.batch_size, 1])
            flipped_idx = np.random.choice(np.arange(len(true_labels)),
                                           size=int(noise_probability * len(true_labels)))
            true_labels[flipped_idx] = 1 - true_labels[flipped_idx]

            generated_labels = np.ones((self.config.batch_size, 1)) - np.random.uniform(
                low=0.0, high=0.1, size=[self.config.batch_size, 1])
            flipped_idx = np.random.choice(np.arange(len(generated_labels)),
                                           size=int(noise_probability * len(generated_labels)))
            generated_labels[flipped_idx] = 1 - generated_labels[flipped_idx]

            # ---------------------
            #  Train Discriminator
            # ---------------------
            images = self.sess.run(self.data.image)
            gen_images = self.model.generator.predict(noise)
            d_loss_real = self.model.discriminator.train_on_batch(images, true_labels)
            d_loss_fake = self.model.discriminator.train_on_batch(gen_images, generated_labels)
            d_loss = 0.5 * np.add(d_loss_real, d_loss_fake)

            # ---------------------
            #  Train Generator
            # ---------------------

            # Train the generator (wants discriminator to mistake images as real)
            g_loss = self.model.combined.train_on_batch(noise, true_labels)

            # Plot the progress
            print("%d [D loss: %f, acc.: %.2f%%] [G loss: %f]" % (epoch, d_loss[0], 100 * d_loss[1], g_loss))

            if epoch % self.config.num_epochs_to_test == 0:
                r, c = 5, 5
                noise = np.random.normal(0, 1, (r * c, self.config.noise_dim))
                gen_imgs = self.model.generator.predict(noise)

                # Rescale images 0 - 1
                gen_imgs = 0.5 * gen_imgs + 0.5

                fig, axs = plt.subplots(r, c)
                cnt = 0
                for i in range(r):
                    for j in range(c):
                        axs[i, j].imshow(gen_imgs[cnt, :, :, 0], cmap='gray')
                        axs[i, j].axis('off')
                        cnt += 1
                fig.savefig(self.config.step_generation_dir + 'image_at_epoch_{:04d}.png'.format(epoch))
                plt.close()
        # Save the model
