class CursorCli < Formula
  desc "CLI tool to run Cursor AI in a Docker container"
  homepage "https://github.com/commure/homebrew-packages"
  url "https://raw.githubusercontent.com/commure/homebrew-packages/main/tools/cursor-cli.py"
  version "1.0.0"
  sha256 :no_check
  license "MIT"

  depends_on "python@3"

  def install
    # Rewrite shebang to use Homebrew's python
    inreplace "cursor-cli.py", "#!/usr/bin/env python3", "#!#{Formula["python@3"].opt_bin}/python3"
    bin.install "cursor-cli.py" => "cursor-cli"
  end

  def caveats
    <<~EOS
      cursor-cli requires Docker to be installed and running.

      Configuration files are stored in:
        ~/.config/cursor-cli/cursor-docker/Dockerfile
        ~/.config/cursor-cli/cursor-docker/docker-args

      You can add custom docker run arguments to the docker-args file.
    EOS
  end

  test do
    assert_match "Run Cursor AI agent", shell_output("#{bin}/cursor-cli --help")
    assert_match "cursor-cli version", shell_output("#{bin}/cursor-cli version")
  end
end
