"""
tests for the enumerate command
"""

import pscheduler

class EnumerateTest(pscheduler.ToolEnumerateUnitTest):
    name = 'owping'
    tests=['latency']
    preference=0
        
if __name__ == '__main__':
    unittest.main()


