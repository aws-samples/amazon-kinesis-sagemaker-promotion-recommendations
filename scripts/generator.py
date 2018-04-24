# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Generates log and buy data at intervals.


# Click format:
# userid	offerid	countrycode	category	merchant	utcdate	rating
# fa937b779184527f12e2d71c711e6411236d1ab59f8597d7494af26d194f0979	c5f63750c2b5b0166e55511ee878b7a3	de	100020213	f3c93baa0cf4430849611cedb3a40ec4094d1d370be8417181da5d13ac99ef3d	2016-06-14 17:28:47.0	0

import numpy as np
import os,binascii
import sys
import time

# initialize our random generator
np.seed = 600

# reference data
products = ['f3c93baa0cf4430849611cedb3a40ec4094d1d370be8417181da5d13ac99ef3d','21a509189fb0875c3732590121ff3fc86da770b0628c1812e82f023ee2e0f683','b042951fdb45ddef8ba6075ced0e5885bc2fa4c4470bf790432e606d85032017','4740b6c83b6e12e423297493f234323ffd1c991f3d4496a71daebbef01d6dcf0','8bf8f87492a799528235c04bb18ff2d12db5058ff6e9a07041739be984a72df9','8497a9dd86ab3b7f192f2e65994b972787bdcdc6b501b48dab19eaa4737ca148','eb49b22a1bbd88fbdf614e3494326c3d2dd853104bff8c5adeaa99a143bdf7d2','10698b6475abd54c5c6d1724d6f51cb795234c23a23daf1bdef1886a8ae522b5','26467f203f42913b6bc575fd4adc89ad66c5db082c8ab90cfc7bb3a5ab1b0ddc','458f4e0daefe1808fd738aaa6613ef3d365d44865606f40c56b3fb554b8fd248','ac26975cf46eae9898b7d906bdfbbf99ce7813ffc3f9b7c42163a55e02e81516','6f529242bbc6dfa46a35f7b9d37a32cd11a0838f204c24f95615d29d2d363ada','ff1bd73f19ccc09842c0b0ad14ff0402e91324cdf924aa3a6a39bfd8c2d9acb3','19e54986c139665f0bc1aee6073618a4dd2cbdbe577a1b51989b2cfd96f43eb3','ea760083815933f4f181ffd989b03fb5398b127dc194c08e89b2f35edf11f21f','81dc9575e12600c50cca637701215bdf3d923eebcb08cc4c67fd928103c4931a','154f65f908a7406826ed6408a156db1bdb82f8f514dffc9c344dfba31ace8520','234e511622f9e1377531dd2df04911360b2d90e18af5b9f78dc58e7d605d4136','66863da8db7e6c51bed5eccc89a91f756e4baee85ad4469e15f0a0cc70f7afdb','0708f809769d6eb4f49d3f6cf6c09e69c754f1337a21b0d5d5a0d0f2c712271e']
users = ['andy','bob','charlie','darlene','ed','francis','gene','irene','henry','lena','mark']
categories = ['100020213','174201','113501','164401','141601','126701','6513','135901','100544023','100434023']
ads = ['0f2fcf95319f5c1e5745371351f521e5','19754ec121b3a99fff3967646942de67','5e378677ca9bb41114562e84001c8516','be83df9772ec47fd210b28091138ff11','3735290a415dc236bacd7ed3aa03b2d5','a5fc37404646ac3d34118489cdbfb341','3c9af92d575a330167fb61dda93b5783','c5f63750c2b5b0166e55511ee878b7a3','241145334525b9b067b15de4fd7a0df1','60253e351dee27e77cd50366585517a3','0c2c89e5fe431aae53fb1ae058770fa2', '5ac4398e4d8ad4167a57b43e9c724b18', 'eb0389774fca117ee06c5c02a6ba76af', 'ccbdecfb71d4a0a7e836a4a4b1e69c97', 'fe8efbbd8879b615478cf7314b3b87ba', '0576e74e809b3b6f04db1fd98c8c9afb', 'ebb77a97cfdfd01c8b2f5cbffb1d5627', '6b989e6ea6d423160c8b30beb8240946', '72d34a12b35de79a46de4fa2298a349b', '56691dbb7196e6114c95306094239118']
countries = ['us','gb','de','fr']

if len(sys.argv) != 5:
    print("Usage: {0} <number of samples> <probability of sale> <click file> <prob that ad used>".format(sys.argv[0]))
    sys.exit(1)

num_samples = int(sys.argv[1])
prob_buy = float(sys.argv[2])
click_file = sys.argv[3]
prob_ad = float(sys.argv[4])

for i in range(1, num_samples+1):
    print("Generating sample {0}".format(i))

    ctime = time.time()
    product = np.random.choice(products)
    countrycode = np.random.choice(countries)
    user = np.random.choice(users)
    category = np.random.choice(categories)
    ad = '0' 
    if np.random.sample() < prob_ad:
        ad = np.random.choice(ads)
    quantity = 0
    if np.random.sample() < prob_buy:
        quantity = 1

    # userid	offerid	countrycode	category	merchant	utcdate	rating
    with open(click_file, 'a') as cfile:
        cfile.write("{0},{1},{2},{3},{4},{5},{6}\n".format(user, ad, countrycode, category, product, ctime, quantity))

    time.sleep(1)
