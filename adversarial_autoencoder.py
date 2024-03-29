import tensorflow as tf
import numpy as np
import datetime
import os
from keras.preprocessing.image import ImageDataGenerator
import matplotlib.pyplot as plt
from matplotlib import gridspec

# from tensorflow.examples.tutorials.mnist import input_data
tf.reset_default_graph()
# Progressbar
# bar = progressbar.ProgressBar(widgets=['[', progressbar.Timer(), ']', progressbar.Bar(), '(', progressbar.ETA(), ')'])

# Get the MNIST data
# mnist = input_data.read_data_sets('./Data', one_hot=True)

# Parameters
image_data_count = 7696
image_width_height = 300
input_dim = image_width_height*image_width_height
n_l1 = 1000
n_l2 = 1000
z_dim = 3
batch_size = 16
n_epochs = 100
learning_rate = 0.001
beta1 = 0.9
results_path = './Results/Adversarial_Autoencoder'
train_data_dir = '/home/gwoo/Documents/Data/png'
conv_depth_mult = 4


def im2double(im):
    max_val = 255
    out = (max_val - im.astype('float')) / max_val
    return out

train_datagen = ImageDataGenerator(
    preprocessing_function=im2double,
    horizontal_flip=False)
train_generator = train_datagen.flow_from_directory(
    train_data_dir,
    target_size=(image_width_height, image_width_height),
    batch_size=batch_size,
    color_mode='grayscale',
    class_mode=None)

# Placeholders for input data and the targets
x_input = tf.placeholder(dtype=tf.float32, shape=[batch_size, input_dim], name='Input')
x_target = tf.placeholder(dtype=tf.float32, shape=[batch_size, input_dim], name='Target')
real_distribution = tf.placeholder(dtype=tf.float32, shape=[batch_size, z_dim], name='Real_distribution')
decoder_input = tf.placeholder(dtype=tf.float32, shape=[1, z_dim], name='Decoder_input')


def form_results():
    """
    Forms folders for each run to store the tensorboard files, saved models and the log files.
    :return: three string pointing to tensorboard, saved models and log paths respectively.
    """
    folder_name = "/{0}_{1}_{2}_{3}_{4}_{5}_Adversarial_Autoencoder". \
        format(datetime.datetime.now(), z_dim, learning_rate, batch_size, n_epochs, beta1)
    tensorboard_path = results_path + folder_name + '/Tensorboard'
    saved_model_path = results_path + folder_name + '/Saved_models/'
    log_path = results_path + folder_name + '/log'
    if not os.path.exists(results_path + folder_name):
        os.makedirs(results_path + folder_name)
        os.makedirs(tensorboard_path)
        os.makedirs(saved_model_path)
        os.mkdir(log_path)
    return tensorboard_path, saved_model_path, log_path


def generate_image_grid(sess, op):
    """
    Generates a grid of images by passing a set of numbers to the decoder and getting its output.
    :param sess: Tensorflow Session required to get the decoder output
    :param op: Operation that needs to be called inorder to get the decoder output
    :return: None, displays a matplotlib window with all the merged images.
    """
    x_points = np.arange(-10, 10, 1.5).astype(np.float32)
    y_points = np.arange(-10, 10, 1.5).astype(np.float32)
    k_points = np.arange(-10, 10, 1.5).astype(np.float32)

    nx, ny, = len(x_points), len(y_points)

    for k in k_points:
        plt.subplot()
        gs = gridspec.GridSpec(nx, ny, hspace=0.05, wspace=0.05)

        for i, g in enumerate(gs):
            z = np.concatenate(([x_points[int(i / ny)]], [y_points[int(i % nx)]], [k]))
            z = np.reshape(z, (1, 3))
            x = sess.run(op, feed_dict={decoder_input: z})
            ax = plt.subplot(g)
            img = np.array(x.tolist()).reshape(image_width_height, image_width_height)
            ax.imshow(img, cmap='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_aspect('auto')
        plt.show()


def get_filter(depth_1, depth_2):
    return tf.Variable(tf.truncated_normal([5, 5, depth_1, depth_2], stddev=0.01))


def convolution(x, name):
    """
    Used to create a dense layer.
    :param x: input tensor to the convolution layer
    :param name: name of the entire convolution layer.i.e, variable scope name.
    :return: tensor with shape [batch, w, h, 4]
    """
    with tf.variable_scope(name, reuse=None):
        in_depth = int(x.get_shape()[3])
        out_depth = int(in_depth * conv_depth_mult)
        conv = tf.nn.conv2d(
            input=x,
            filter=get_filter(in_depth, out_depth),
            strides=[1, 2, 2, 1],
            padding="SAME"
        )
        bias = tf.get_variable("bias", shape=[1], initializer=tf.constant_initializer(0.0))
        out = tf.add(conv, bias, name='matmul')
        return out


def deconvolution(x, name):
    """
    Used to create a dense layer.
    :param x: input tensor to the deconvolution layer
    :param name: name of the entire convolution layer.i.e, variable scope name.
    :return: tensor with shape [batch, w, h, 1]
    """
    with tf.variable_scope(name, reuse=None):
        in_depth = int(x.get_shape()[3])
        out_depth = int(in_depth / conv_depth_mult)
        in_width_height = int(x.get_shape()[1])
        out_width_height = in_width_height * 2
        deconv = tf.nn.conv2d_transpose(
            value=x,
            filter=get_filter(out_depth, in_depth),
            output_shape=[batch_size, out_width_height, out_width_height, out_depth],
            strides=[1, 2, 2, 1],
            padding="SAME"
        )
        bias = tf.get_variable("bias", shape=[1], initializer=tf.constant_initializer(0.0))
        out = tf.add(deconv, bias, name='matmul')
        return out


def dense(x, n1, n2, name):
    """
    Used to create a dense layer.
    :param x: input tensor to the dense layer
    :param n1: no. of input neurons
    :param n2: no. of output neurons
    :param name: name of the entire dense layer.i.e, variable scope name.
    :return: tensor with shape [batch_size, n2]
    """
    with tf.variable_scope(name, reuse=None):
        weights = tf.get_variable("weights", shape=[n1, n2],
                                  initializer=tf.random_normal_initializer(mean=0., stddev=0.01))
        bias = tf.get_variable("bias", shape=[n2], initializer=tf.constant_initializer(0.0))
        out = tf.add(tf.matmul(x, weights), bias, name='matmul')
        return out


# The autoencoder network
def encoder(x, reuse=False):
    """
    Encode part of the autoencoder.
    :param x: input to the autoencoder
    :param reuse: True -> Reuse the encoder variables, False -> Create or search of variables before creating
    :return: tensor which is the hidden latent variable of the autoencoder.
    """
    if reuse:
        tf.get_variable_scope().reuse_variables()
    with tf.name_scope('Encoder'):
        x_image_input = tf.reshape(x, [batch_size, image_width_height, image_width_height, 1])
        e_conv_1 = tf.nn.relu(convolution(x_image_input, 'e_conv_1'))
        e_conv_2 = tf.nn.relu(convolution(e_conv_1, 'e_conv_2'))
        e_conv_2_flat = tf.reshape(e_conv_2, [batch_size, -1])
        e_dense_1 = tf.nn.relu(dense(e_conv_2_flat, input_dim, n_l2, 'e_dense_1'))
        latent_variable = dense(e_dense_1, n_l2, z_dim, 'e_latent_variable')
        return latent_variable


def decoder(x, reuse=False):
    """
    Decoder part of the autoencoder.
    :param x: input to the decoder
    :param reuse: True -> Reuse the decoder variables, False -> Create or search of variables before creating
    :return: tensor which should ideally be the input given to the encoder.
    """
    if reuse:
        tf.get_variable_scope().reuse_variables()
    with tf.name_scope('Decoder'):
        decoder_batch_size = int(x.get_shape()[0])
        d_dense_1 = tf.nn.relu(dense(x, z_dim, n_l2, 'd_dense_1'))
        d_dense_2 = tf.nn.relu(dense(d_dense_1, n_l2, input_dim, 'd_dense_2'))
        d_dense_2_image = tf.reshape(d_dense_2, [decoder_batch_size, int(image_width_height/4), int(image_width_height/4), 16])
        d_conv_1 = tf.nn.relu(deconvolution(d_dense_2_image, 'd_conv_1'))
        d_conv_2 = tf.nn.sigmoid(deconvolution(d_conv_1, 'd_conv_2'))
        output_flat = tf.reshape(d_conv_2, [decoder_batch_size, -1])
        return output_flat


def discriminator(x, reuse=False):
    """
    Discriminator that is used to match the posterior distribution with a given prior distribution.
    :param x: tensor of shape [batch_size, z_dim]
    :param reuse: True -> Reuse the discriminator variables,
                  False -> Create or search of variables before creating
    :return: tensor of shape [batch_size, 1]
    """
    if reuse:
        tf.get_variable_scope().reuse_variables()
    with tf.name_scope('Discriminator'):
        dc_den1 = tf.nn.relu(dense(x, z_dim, n_l1, name='dc_den1'))
        dc_den2 = tf.nn.relu(dense(dc_den1, n_l1, n_l2, name='dc_den2'))
        dc_den3 = tf.nn.relu(dense(dc_den2, n_l1, n_l2, name='dc_den3'))
        output = dense(dc_den3, n_l2, 1, name='dc_output')
        return output


def train(train_model=True):
    """
    Used to train the autoencoder by passing in the necessary inputs.
    :param train_model: True -> Train the model, False -> Load the latest trained model and show the image grid.
    :return: does not return anything
    """
    with tf.variable_scope(tf.get_variable_scope()):
        encoder_output = encoder(x_input)
        decoder_output = decoder(encoder_output)

    with tf.variable_scope(tf.get_variable_scope()):
        d_real = discriminator(real_distribution)
        d_fake = discriminator(encoder_output, reuse=True)

    with tf.variable_scope(tf.get_variable_scope()):
        decoder_image = decoder(decoder_input, reuse=True)

    # Autoencoder loss
    autoencoder_loss = tf.reduce_mean(tf.square(x_target - decoder_output))

    # Discrimminator Loss
    dc_loss_real = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(labels=tf.ones_like(d_real), logits=d_real))
    dc_loss_fake = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(labels=tf.zeros_like(d_fake), logits=d_fake))
    dc_loss = dc_loss_fake + dc_loss_real

    # Generator loss
    generator_loss = tf.reduce_mean(
        tf.nn.sigmoid_cross_entropy_with_logits(labels=tf.ones_like(d_fake), logits=d_fake))

    all_variables = tf.trainable_variables()
    dc_var = [var for var in all_variables if 'dc_' in var.name]
    en_var = [var for var in all_variables if 'e_' in var.name]

    # Optimizers
    autoencoder_optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate,
                                                   beta1=beta1).minimize(autoencoder_loss)
    discriminator_optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate,
                                                     beta1=beta1).minimize(dc_loss, var_list=dc_var)
    generator_optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate,
                                                 beta1=beta1).minimize(generator_loss, var_list=en_var)

    init = tf.global_variables_initializer()

    # Reshape immages to display them
    input_images = tf.reshape(x_input, [-1, image_width_height, image_width_height, 1])
    generated_images = tf.reshape(decoder_output, [-1, image_width_height, image_width_height, 1])

    # Tensorboard visualization
    tf.summary.scalar(name='Autoencoder Loss', tensor=autoencoder_loss)
    tf.summary.scalar(name='Discriminator Loss', tensor=dc_loss)
    tf.summary.scalar(name='Generator Loss', tensor=generator_loss)
    tf.summary.histogram(name='Encoder Distribution', values=encoder_output)
    tf.summary.histogram(name='Real Distribution', values=real_distribution)
    tf.summary.image(name='Input Images', tensor=input_images, max_outputs=1)
    tf.summary.image(name='Generated Images', tensor=generated_images, max_outputs=1)
    summary_op = tf.summary.merge_all()

    # Saving the model
    saver = tf.train.Saver()
    step = 0
    with tf.Session() as sess:
        if train_model:
            tensorboard_path, saved_model_path, log_path = form_results()
            sess.run(init)
            writer = tf.summary.FileWriter(logdir=tensorboard_path, graph=sess.graph)
            for i in range(n_epochs):
                # n_batches = int(mnist.train.num_examples / batch_size)
                n_batches = int(image_data_count / batch_size)
                print("------------------Epoch {}/{}------------------".format(i, n_epochs))
                for b in range(1, n_batches + 1):
                    z_real_dist = np.random.randn(batch_size, z_dim) * 5.
                    # batch_x, _ = mnist.train.next_batch(batch_size)
                    # batch_x = np.squeeze(train_generator.next(), axis=(2,3))
                    batch_x = np.array([data.reshape(input_dim) for data in train_generator.next()])
                    sess.run(autoencoder_optimizer, feed_dict={x_input: batch_x, x_target: batch_x})
                    sess.run(discriminator_optimizer,
                             feed_dict={x_input: batch_x, x_target: batch_x, real_distribution: z_real_dist})
                    sess.run(generator_optimizer, feed_dict={x_input: batch_x, x_target: batch_x})
                    if b % 50 == 0:
                        a_loss, d_loss, g_loss, summary = sess.run(
                            [autoencoder_loss, dc_loss, generator_loss, summary_op],
                            feed_dict={x_input: batch_x, x_target: batch_x,
                                       real_distribution: z_real_dist})
                        writer.add_summary(summary, global_step=step)
                        print("Epoch: {}, iteration: {}".format(i, b))
                        print("Autoencoder Loss: {}".format(a_loss))
                        print("Discriminator Loss: {}".format(d_loss))
                        print("Generator Loss: {}".format(g_loss))
                        with open(log_path + '/log.txt', 'a') as log:
                            log.write("Epoch: {}, iteration: {}\n".format(i, b))
                            log.write("Autoencoder Loss: {}\n".format(a_loss))
                            log.write("Discriminator Loss: {}\n".format(d_loss))
                            log.write("Generator Loss: {}\n".format(g_loss))
                    step += 1

                saver.save(sess, save_path=saved_model_path, global_step=step)
        else:
            # Get the latest results folder
            all_results = os.listdir(results_path)
            all_results.sort()
            load_path = tf.train.latest_checkpoint(results_path + '/' + all_results[-1] + '/Saved_models/')
            print("Load path: {}".format(load_path))
            saver.restore(sess, save_path=load_path)
            generate_image_grid(sess, op=decoder_image)

if __name__ == '__main__':
    train(train_model=True)
