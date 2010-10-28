"""
nose's test loader implements the nosetests functionality
"""

from __future__ import generators

import os
import sys
import unittest
from inspect import isfunction, ismethod
from nose_helper.case import FunctionTestCase, MethodTestCase
from nose_helper.failure import Failure
from nose_helper.config import Config
from nose_helper.selector import defaultSelector
from nose_helper.util import cmp_lineno, isclass, isgenerator, add_path
from nose_helper.util import transplant_class
from nose_helper.suite import ContextSuiteFactory, ContextList

op_normpath = os.path.normpath
op_abspath = os.path.abspath

class TestLoader(unittest.TestLoader):
    """Test loader that extends unittest.TestLoader to support nosetests
    """
    config = None
    workingDir = None
    selector = None
    suiteClass = None
    
    def __init__(self):
        """Initialize a test loader.
        """
        self.config = Config()
        self.selector = defaultSelector(self.config)
        self.workingDir = op_normpath(op_abspath(self.config.workingDir))
        add_path(self.workingDir, self.config)
        self.suiteClass = ContextSuiteFactory(config=self.config)
        unittest.TestLoader.__init__(self)     

    def loadTestsFromGenerator(self, generator, module):
        """The generator function may yield either:
        * a callable, or
        * a function name resolvable within the same module
        """
        def generate(g=generator, m=module):
            try:
                for test in g():
                    test_func, arg = self.parseGeneratedTest(test)
                    if not callable(test_func):
                        test_func = getattr(m, test_func)
                    yield FunctionTestCase(test_func, arg=arg, descriptor=g)
            except KeyboardInterrupt:
                raise
            except:
                exc = sys.exc_info()
                yield Failure(exc[0], exc[1], exc[2])
        return self.suiteClass(generate, context=generator, can_split=False)

    def loadTestsFromModule(self, module):
        """Load all tests from module and return a suite containing
        them.
        """
        tests = []
        test_classes = []
        test_funcs = []
        if self.selector.wantModule(module):
            for item in dir(module):
                test = getattr(module, item, None)
                if isclass(test):
                    if self.selector.wantClass(test):
                        test_classes.append(test)
                elif isfunction(test) and self.selector.wantFunction(test):
                    test_funcs.append(test)
            test_classes.sort(lambda a, b: cmp(a.__name__, b.__name__))
            test_funcs.sort(cmp_lineno)
            tests = map(lambda t: self.makeTest(t, parent=module),
                        test_classes + test_funcs)
        return self.suiteClass(ContextList(tests, context=module))


    def loadTestsFromTestClass(self, cls):
        """Load tests from a test class that is *not* a unittest.TestCase
        subclass.
        """
        def wanted(attr, cls=cls, sel=self.selector):
            item = getattr(cls, attr, None)
            if not ismethod(item):
                return False
            return sel.wantMethod(item)
        cases = [self.makeTest(getattr(cls, case), cls)
                 for case in filter(wanted, dir(cls))]
        return self.suiteClass(ContextList(cases, context=cls))

    def makeTest(self, obj, parent=None):
        try:
            return self._makeTest(obj, parent)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            exc = sys.exc_info()
            return Failure(exc[0], exc[1], exc[2])
    
    def _makeTest(self, obj, parent=None):
        """Given a test object and its parent, return a test case
        or test suite.
        """

        if isinstance(obj, unittest.TestCase):
            return obj
        elif isclass(obj):
            if parent and obj.__module__ != parent.__name__:
                obj = transplant_class(obj, parent.__name__)
            if issubclass(obj, unittest.TestCase):
                return self.loadTestsFromTestCase(obj)
            else:
                return self.loadTestsFromTestClass(obj)
        elif ismethod(obj):
            if parent is None:
                parent = obj.__class__
            if issubclass(parent, unittest.TestCase):
                return parent(obj.__name__)
            else:
                return MethodTestCase(obj)
        elif isfunction(obj):
            if isgenerator(obj):
                return self.loadTestsFromGenerator(obj, parent)
            else:
                return FunctionTestCase(obj)
        else:
            return Failure(TypeError,
                           "Can't make a test from %s" % obj)

    def resolve(self, name, module):
        """Resolve name within module
        """
        obj = module
        parts = name.split('.')
        for part in parts:
            parent, obj = obj, getattr(obj, part, None)
        if obj is None:
            # no such test
            obj = Failure(ValueError, "No such test %s" % name)
        return parent, obj

    def parseGeneratedTest(self, test):
        """Given the yield value of a test generator, return a func and args.
        """
        if not isinstance(test, tuple):         # yield test
            test_func, arg = (test, tuple())
        elif len(test) == 1:                    # yield (test,)
            test_func, arg = (test[0], tuple())
        else:                                   # yield test, foo, bar, ...
            assert len(test) > 1 # sanity check
            test_func, arg = (test[0], test[1:])
        return test_func, arg

