namespace VisorSingularity
{
    /// <summary>
    /// Configuration constants for island loading logic.
    /// </summary>
    public static class IslandConfig
    {
        /// <summary>
        /// Maximum age in seconds for a peer file to be considered "fresh" when loading the default island.
        /// Adjust this value if your environment writes peer files slower than 25 seconds.
        /// </summary>
        public const int ISLAND_PEER_MAX_AGE_SECONDS = 60; // default 60 s
    }
}
