import unittest
import hiddenlayer as hl
import hiddenlayer.ge as ge
import hiddenlayer.transforms as ht


class TestGEParser(unittest.TestCase):

    def test_basics(self):
        p = ge.GEParser(" (hello )")
        self.assertTrue(p.token("(") and p.re(r"\w+") and p.token(")"))

        p = ge.GEParser("[1x1]")
        self.assertTrue(p.condition() == "1x1" and p.index == 5)

        p = ge.GEParser(" [ 1x1 ] ")
        self.assertTrue(p.condition() == "1x1" and p.index == 9)

        p = ge.GEParser("[1x1")
        self.assertTrue(not p.condition() and p.index == 0)

        p = ge.GEParser("Conv[1x1]")
        self.assertTrue(isinstance(p.op(), ge.NodePattern))

        p = ge.GEParser("Conv[1x1]")
        self.assertTrue(isinstance(p.expression(), ge.NodePattern))

        p = ge.GEParser("(Conv[1x1])")
        self.assertTrue(isinstance(p.expression(), ge.NodePattern))

    def test_serial(self):
        p = ge.GEParser("Conv>Conv")
        self.assertTrue(isinstance(p.serial(), ge.SerialPattern))

        p = ge.GEParser("Conv > Conv[1x1]")
        self.assertTrue(isinstance(p.serial(), ge.SerialPattern))

        p = ge.GEParser("Conv > (Conv[1x1] > Conv)")
        self.assertTrue(isinstance(p.serial(), ge.SerialPattern))

        p = ge.GEParser("Conv > Conv[1x1] > Conv")
        self.assertTrue(isinstance(p.serial(), ge.SerialPattern))
        self.assertEqual(p.index, 23)

        p = ge.GEParser("(Conv > Conv[1x1])")
        self.assertTrue(isinstance(p.expression(), ge.SerialPattern))

    def test_parallel(self):
        p = ge.GEParser("Conv|Conv[1x1]")
        self.assertTrue(isinstance(p.parallel(), ge.ParallelPattern))

        p = ge.GEParser("Conv | Conv[1x1]")
        self.assertTrue(isinstance(p.parallel(), ge.ParallelPattern))

        p = ge.GEParser("Conv | (Conv[1x1] | Conv)")
        self.assertTrue(isinstance(p.parallel(), ge.ParallelPattern))

        p = ge.GEParser("Conv | Conv[1x1] | Conv")
        self.assertTrue(isinstance(p.parallel(), ge.ParallelPattern))
        self.assertEqual(p.index, 23)

        p = ge.GEParser("(Conv | Conv[1x1])")
        self.assertTrue(isinstance(p.expression(), ge.ParallelPattern))

    def test_combinations(self):
        p = ge.GEParser("Conv | (Conv[1x1] > Conv)")
        self.assertTrue(isinstance(p.parallel(), ge.ParallelPattern))

        p = ge.GEParser("Conv > (Conv [1x1] | Conv)")
        self.assertTrue(isinstance(p.serial(), ge.SerialPattern))

    def test_parsing(self):
        p = ge.GEParser("Conv")
        self.assertTrue(isinstance(p.parse(), ge.NodePattern))

        p = ge.GEParser("Conv | Conv[1x1] ")
        self.assertTrue(isinstance(p.parse(), ge.ParallelPattern))

        p = ge.GEParser("Conv | (Conv[1x1] > Conv)")
        self.assertTrue(isinstance(p.parse(), ge.ParallelPattern))

        p = ge.GEParser("(Conv | (Conv[1x1] > Conv))")
        self.assertTrue(isinstance(p.parse(), ge.ParallelPattern))


class TestGraph(unittest.TestCase):
    def test_directed_graph(self):
        g = hl.Graph()
        g.add_node("a")
        g.add_node("b")
        g.add_node("c")
        g.add_edge("a", "b")
        g.add_edge("b", "c")

        self.assertEqual(g[g.incoming("b")[0]], "a")
        self.assertEqual(g[g.outgoing("b")[0]], "c")
        g.replace(["b"], "x")
        self.assertEqual(sorted(list(g.nodes.values())), sorted(["a", "c", "x"]))
        self.assertEqual(g[g.incoming("x")[0]], "a")
        self.assertEqual(g[g.outgoing("x")[0]], "c")


class TestPatterns(unittest.TestCase):
    def test_basics(self):
        g = hl.Graph()
        a = hl.Node(uid="a", name="a", op="a")
        b = hl.Node(uid="b", name="b", op="b")
        c = hl.Node(uid="c", name="c", op="c")
        d = hl.Node(uid="d", name="d", op="d")
        e = hl.Node(uid="e", name="e", op="e")
        g.add_node(a)
        g.add_node(b)
        g.add_node(c)
        g.add_node(d)
        g.add_node(e)
        g.add_edge(a, b)
        g.add_edge(b, c)
        g.add_edge(b, d)
        g.add_edge(c, e)
        g.add_edge(d, e)

        rule = ge.GEParser("a > b").parse()
        self.assertIsInstance(rule, ge.SerialPattern)
        match, following = rule.match(g, a)
        self.assertTrue(match)
        self.assertCountEqual(following, [c, d])
        match, following = rule.match(g, b)
        self.assertFalse(match)

        rule = ge.GEParser("b > c").parse()
        self.assertIsInstance(rule, ge.SerialPattern)
        match, following = rule.match(g, b)
        self.assertFalse(match)

        rule = ge.GEParser("c | d").parse()
        self.assertIsInstance(rule, ge.ParallelPattern)
        match, following = rule.match(g, [c, d])
        self.assertTrue(match)
        self.assertEqual(following, e)
        match, following = rule.match(g, [c])
        self.assertTrue(match)
        self.assertEqual(following, e)
        match, following = rule.match(g, d)
        self.assertTrue(match)
        self.assertEqual(following, e)
        match, following = rule.match(g, b)
        self.assertFalse(match)

        rule = ge.GEParser("a > b > (c | d)").parse()
        self.assertIsInstance(rule, ge.SerialPattern)
        match, following = rule.match(g, a)
        self.assertTrue(match, following)

        rule = ge.GEParser("(a > b) > (c | d)").parse()
        self.assertIsInstance(rule, ge.SerialPattern)
        match, following = rule.match(g, a)
        self.assertTrue(match)

        rule = ge.GEParser("a > b > (c | d) > e").parse()
        self.assertIsInstance(rule, ge.SerialPattern)
        match, following = rule.match(g, a)
        self.assertTrue(match)

        rule = ge.GEParser("(c | d) > e").parse()
        self.assertIsInstance(rule, ge.SerialPattern)
        match, following = rule.match(g, [c, d])
        self.assertTrue(match)

    def test_search(self):
        g = hl.Graph()
        a = hl.Node(uid="a", name="a", op="a")
        b = hl.Node(uid="b", name="b", op="b")
        c = hl.Node(uid="c", name="c", op="c")
        d = hl.Node(uid="d", name="d", op="d")
        g.add_node(a)
        g.add_node(b)
        g.add_node(c)
        g.add_node(d)
        g.add_edge(a, b)
        g.add_edge(b, c)
        g.add_edge(b, d)

        pattern = ge.GEParser("a > b").parse()
        match, following = g.search(pattern)
        self.assertCountEqual(match, [a, b])
        self.assertCountEqual(following, [c, d])

        pattern = ge.GEParser("b > (c | d)").parse()
        match, following = g.search(pattern)
        self.assertCountEqual(match, [b, c, d])
        self.assertEqual(following, [])

        pattern = ge.GEParser("c|d").parse()
        match, following = g.search(pattern)
        self.assertCountEqual(match, [c, d])
        self.assertEqual(following, [])


class TestTransforms(unittest.TestCase):
    def build_graph(self):
        # TODO: can't do it because I need to return
        #       variables, a, b, c, ...etc.
        #       Find better solution
        pass

    def test_regex(self):
        g = hl.Graph()
        a = hl.Node(uid="a", name="a", op="a")
        b = hl.Node(uid="b", name="b", op="b")
        c = hl.Node(uid="c", name="c", op="c")
        d = hl.Node(uid="d", name="d", op="d")
        g.add_node(a)
        g.add_node(b)
        g.add_node(c)
        g.add_node(d)
        g.add_edge(a, b)
        g.add_edge(b, c)
        g.add_edge(b, d)

        t = ht.Rename(op=r"a", to="bbb")
        t.apply(g)
        self.assertEqual(a.op, "bbb")

        t = ht.Rename(op=r"b(.*)", to=r"x\1")
        t.apply(g)
        self.assertEqual(a.op, "xbb")
        self.assertEqual(b.op, "x")

    def test_fold(self):
        g = hl.Graph()
        a = hl.Node(uid="a", name="a", op="a")
        b = hl.Node(uid="b", name="b", op="b")
        c = hl.Node(uid="c", name="c", op="c")
        d = hl.Node(uid="d", name="d", op="d")
        g.add_node(a)
        g.add_node(b)
        g.add_node(c)
        g.add_node(d)
        g.add_edge(a, b)
        g.add_edge(b, c)
        g.add_edge(b, d)

        t = ht.Fold("a > b", "ab")
        t.apply(g)
        self.assertEqual(g[g.incoming(c)[0]].op, "ab")

    def test_parallel_fold(self):
        g = hl.Graph()
        a = hl.Node(uid="a", name="a", op="a")
        b = hl.Node(uid="b", name="b", op="b")
        c = hl.Node(uid="c", name="c", op="c")
        d = hl.Node(uid="d", name="d", op="d")
        e = hl.Node(uid="e", name="e", op="e")
        g.add_node(a)
        g.add_node(b)
        g.add_node(c)
        g.add_node(d)
        g.add_node(e)
        g.add_edge(a, b)
        g.add_edge(b, c)
        g.add_edge(a, d)
        g.add_edge(c, e)
        g.add_edge(d, e)

        t = ht.Fold("((b > c) | d) > e", "bcde")
        t.apply(g)
        self.assertEqual(g[g.outgoing(a)[0]].op, "bcde")

    def test_prune(self):
        g = hl.Graph()
        a = hl.Node(uid="a", name="a", op="a")
        b = hl.Node(uid="b", name="b", op="b")
        c = hl.Node(uid="c", name="c", op="c")
        d = hl.Node(uid="d", name="d", op="d")
        e = hl.Node(uid="e", name="e", op="e")
        g.add_node(a)
        g.add_node(b)
        g.add_node(c)
        g.add_node(d)
        g.add_node(e)
        g.add_edge(a, b)
        g.add_edge(b, c)
        g.add_edge(a, d)
        g.add_edge(c, e)
        g.add_edge(d, e)

        t = ht.Prune("e")
        t.apply(g)
        self.assertFalse(g.outgoing(d))


if __name__ == "__main__":
    unittest.main()