TDD in practice
===============

Simple example how to create a plugin with TDD principles.

First, activate your virtualenv and install the dependencies needed for testing::

  source YOUR-ENV-DIR/bin/activate
  pip install pytest mock vcrpy

Create test
-----------

Write new test case called ``tests/test_hello.py``.

.. testcode::

   class TestHello(object):

       config = """
           tasks:
             test:
               mock:                 # let's use this plugin to create test data
                 - {title: 'foobar'} # we can omit url if we do not care about it, in this case mock will add random url
               hello: yes            # our plugin, no relevant configuration yet ...
       """

       # The flexget test framework provides the execute_task fixture, which is a function to run tasks
       def test_feature(self, execute_task):
         # run the task
         execute_task('test')

Try running the test with py.test::

  py.test tests/test_hello.py

It should complain that the plugin hello does not exists, that's because we
haven't yet created it. Let's do that next.

Create plugin
-------------

Create new file called ``flexget/plugins/output/hello.py``.

Within this file we will add our plugin.

.. testcode::

   from __future__ import unicode_literals, division, absolute_import

   from flexget import plugin
   from flexget.event import event


   class Hello(object):
       pass

   @event('plugin.register')
   def register_plugin():
       plugin.register(Hello, 'hello', api_ver=2)

After this the unit tests should pass again. Try running them.


Add test
--------

Now our example plugin will be very simple, we just want to add
new field to each entry called ``hello`` with value ``True``.

Let's supplement the testsuite with the test.


.. testcode::

   class TestHello(object):

       config = """
           tasks:
             test:
               mock:                 # let's use this plugin to create test data
                 - {title: 'foobar'} # we can omit url if we do not care about it, in this case mock will add random url
               hello: yes            # our plugin, no relevant configuration yet ...
       """

       def test_feature(self, execute_task):
         # run the task
         task = execute_task('test')
         for entry in task.entries:
             assert entry.get('hello') == True

This should fail as we do not currently have such functionality in the plugin.


Add functionality to plugin
---------------------------

Continue by implementing the test case.

.. testcode::

   from __future__ import unicode_literals, division, absolute_import

   from flexget import plugin
   from flexget.event import event


   class Hello(object):
       def on_task_filter(self, task, config):
           for entry in task.entries:
               entry['hello'] = True

   @event('plugin.register')
   def register_plugin():
       plugin.register(Hello, 'hello', api_ver=2)


Summary
-------

This demonstrates main principle and workflow behind TDD and shows how it can
be achieved with FlexGet.
