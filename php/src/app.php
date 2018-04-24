<?php

/* 
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
*/

require __DIR__ . '/../vendor/autoload.php';
date_default_timezone_set('America/Denver');

use Silex\Application;
use Silex\Provider\TwigServiceProvider;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;

// Setup the application
$app = new Application();
$app->register(new TwigServiceProvider, array(
    'twig.path' => __DIR__ . '/templates',
));
$app->register(new Silex\Provider\SessionServiceProvider());

$app->before(function ($request) {
    $request->getSession()->start();
});

$app->match('/login', function (Request $request) use ($app) {
    if (null === $session = $app['session']->getId()) {
        $session = 'NOSESSION';
    }
    if (null === $user = $app['session']->get('user')) {
        $userid = 'NOUSER';
    }
    else {
        $userid = $user['username'];
    }

    $alert = null;
    $uname = '';
    // If the form was submitted, process the input
    if ('POST' == $request->getMethod()) {
        try {
            $uname = $request->request->get('uname');
            $app['session']->set('user', array('username' => $uname));

        } catch (Exception $e) {
            // Display an error message
            $alert = array('type' => 'error', 'message' => $e->getMessage());
        }
    }

    return $app['twig']->render('account.twig', array(
        'title' => 'Your Account',
        'user'     => $uname,
        'alert' => $alert,
    ));
});

$app->match('/buy', function (Request $request) use ($app) {
    if (null === $session = $app['session']->getId()) {
        $session = 'NOSESSION';
    }
    $userid = '';
    if (null === $user = $app['session']->get('user')) {
        return $app['twig']->render('login.twig', array(
        'title'    => 'Login',
        ));
    }
    else {
        $userid = $user['username'];
    }

    $alert = null;
    // If the form was submitted, process the input
    if ('POST' == $request->getMethod()) {
        try {
            $category = $request->request->get('Category');
            $price = $request->request->get('Price');
            $item = $request->request->get('Item');
            $ad = $request->request->get('Ad');
            $quantity = $request->request->get('Quantity');
            $countrycode = 'us';

        } catch (Exception $e) {
            // Display an error message
            $alert = array('type' => 'error', 'message' => $e->getMessage());
        }
        //  Each line is a CSV in format: userid	offerid	countrycode	category	merchant	utcdate	rating
        $log  = $userid.",".$ad.",".$countrycode.",".$category.",".$item.",".microtime(true).",1".PHP_EOL;
        file_put_contents('/var/www/logs/log_'.date("j.n.Y").'.txt', $log, FILE_APPEND);

        return $app['twig']->render('index.twig', array(
            'title'    => 'Online Store',
        ));
    }
    else {
        // GET params
        $params = $request->query->all();

        // Params which are on the PATH_INFO
        foreach ( $request->attributes as $key => $val )
        {
            // on the attributes ParamaterBag there are other parameters
            // which start with a _parametername. We don't want them.
            if ( strpos($key, '_') != 0 )
            {
                $params[ $key ] = $val;
            }

        }

        $category = $params['Category'];
        $price = $params['Price'];
        $item = $params['Item'];
        $description = $params['Desc'];
        $countrycode = 'us';
        $ad = '';

        $log  = $userid.",".$ad.",".$countrycode.",".$category.",".$item.",".microtime(true).",0".PHP_EOL;
        file_put_contents('/var/www/logs/log_'.date("j.n.Y").'.txt', $log, FILE_APPEND);

        return $app['twig']->render('buy.twig', array(
            'title' => 'Online Ordering',
            'Item'     => $item,
            'Price'     => $price,
            'Category'     => $category,
            'Desc'     => $description,
            'alert' => $alert,
        ));
    }

});

$app->get('/account', function () use ($app) {
    if (null === $session = $app['session']->getId()) {
        $session = 'NOSESSION';
    }
    if (null === $user = $app['session']->get('user')) {
        $userid = 'NOUSER';
    }
    else {
        $userid = $user['username'];
    }

    if (null === $user = $app['session']->get('user')) {
        return $app['twig']->render('login.twig', array(
        'title'    => 'Login',
        ));
    }

    return $app['twig']->render('account.twig', array(
        'title'    => 'Account',
        'user'     => $userid,
    ));
});


// Handle the index page
$app->match('/', function () use ($app) {
    if (null === $session = $app['session']->getId()) {
        $session = 'NOSESSION';
    }
    if (null === $user = $app['session']->get('user')) {
        $userid = 'NOUSER';
    }
    else {
        $userid = $user['username'];
    }

    return $app['twig']->render('index.twig', array(
        'title'    => 'Online Store',
    ));
});

$app->run();
