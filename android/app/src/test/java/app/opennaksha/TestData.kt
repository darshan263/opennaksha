package app.opennaksha

/** Synthetic catalog fixtures (example.test URLs only) from src/test/resources/catalog/. */
object TestData {
    fun read(path: String): String =
        requireNotNull(javaClass.classLoader!!.getResource(path)) { "missing test resource $path" }.readText()

    val index get() = read("catalog/index.json")
    val city get() = read("catalog/cities/testcity.json")
    val changes get() = read("catalog/changes.json")
}
