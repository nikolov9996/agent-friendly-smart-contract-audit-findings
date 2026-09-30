---
id: 22649
severity: "High"
---

# It is possible to DoS batch auctions by sub-

## Description

Bidders can submit invalid points for the AltBn128 elliptic curve. The invalid points will make the decrypting process always revert, effectively DoSing the auction process, and locking funds forever in the protocol.
Axis finance supports a sealed-auction type of auctions, which is achieved in the Encrypted Marginal Price Auction module by leveraging the ECIES encryption scheme. Axis will specifically use a simplified ECIES implementation that uses the AltBn128 curve, which is a curve with generator point (1,2) and the following formula:
y2 = x3 + 3
Bidders will submit encrypted bids to the protocol. One of the parameters required to be submitted by the bidders so that bids can later be decrypted is a public key that will be used in the EMPA decryption process:
```solidity
// EMPAM.sol
function _bid(
    uint96 lotId_,
    address bidder_,
    address referrer_,
    uint96 amount_,
    bytes calldata auctionData_
) internal override returns (uint64 bidId) {
    // Decode auction data
    (uint256 encryptedAmountOut, Point memory bidPubKey) = abi.decode(auctionData_, (uint256, Point));
    ...
    // Check that the bid public key is a valid point for the encryption library
    if (!ECIES.isValid(bidPubKey)) revert Auction_InvalidKey();
    ...
    return bidId;
}
```
As shown in the code snippet, bidders will submit a bidPubKey, which consists in an x and y coordinate (this is actually the public key, which can be represented as a point with x and y coordinates over an elliptic curve).
The bidPubKey point will then be validated by the ECIES library’s isValid() function. Essentially, this function will perform three checks:
1. Verify that the point provided is on the AltBn128 curve
2. Ensure the x and y coordinates of the point provided don’t correspond to the generator point (1, 2)
3. Ensure that the x and y coordinates of the point provided don’t corrspond to the point at infinity (0,0)
```solidity
// ECIES.sol
function isOnBn128(Point memory p) public pure returns (bool) {
    // check if the provided point is on the bn128 curve y**2 = x**3 + 3, which has generator point (1, 2)
    return _fieldmul(p.y, p.y) == _fieldadd(_fieldmul(p.x, _fieldmul(p.x, p.x)), 3);
}

/// @notice Checks whether a point is valid. We consider a point valid if it is on the curve and not the generator point or the point at infinity.
function isValid(Point memory p) public pure returns (bool) {
    return isOnBn128(p) && !(p.x == 1 && p.y == 2) && !(p.x == 0 && p.y == 0);
}
```
Although these checks are correct, one important check is missing in order to consider that the point is actually a valid point in the AltBn128 curve.
As a summary, ECC incorporates the concept of finite fields. Essentially, the elliptic curve is considered as a square matrix of size pxp, where p is the finite field (in our case, the finite field defined in Axis’ ECIES.sol library is stord in the FIELD_MODULUS constant with a value of 21888242871839275222246405745257275088696311157297823662689037894645226208583).
The curve equation then takes this form:
y2 = x3 + ax + b(modp)
that has an x or y coordinate greater than the modulus will fall outside of the matrix, thus being invalid. In other words, if x > p or y > p, the point should be considered invalid. However, as shown in the previous snippet of code, this check is not performed in Axis’ ECIES implementation.
This enables a malicious bidder to provide an invalid point with an x or y coordinate greater than the field, but that still passes the checked conditions in the ECIES library. The isValid() check will pass and the bid will be successfully submitted, although the public key is theoretically invalid.
This leads us to the second part of the attack. When the auction concludes, the decryption process will begin. The process consists in:
1. Calling the decryptAndSortBids() function. This will trigger the internal only set the status of the auction to Decrypted if ALL the bids submitted have been decrypted. Otherwise, the auction can’t continue.
2. _decryptAndSortBids() will call the internal _decrypt() function for each of the bids submittted
3. _decrypt() will finally call the ECIES’ decrypt() function so that the bid can be decrypted:
```solidity
// EMPAM.sol
function _decrypt(
    uint96 lotId_,
    uint64 bidId_,
    uint256 privateKey_
) internal view returns (uint256 amountOut) {
    // Load the encrypted bid data
    EncryptedBid memory encryptedBid = encryptedBids[lotId_][bidId_];
    // Decrypt the message
    // We expect a salt calculated as the keccak256 hash of lot id, bidder, and amount to provide some (not total) uniqueness to the encryption, even if the same shared secret is used
    Bid storage bidData = bids[lotId_][bidId_];
    uint256 message = ECIES.decrypt(
        encryptedBid.encryptedAmountOut,
        encryptedBid.bidPubKey,
        privateKey_,
        uint256(keccak256(abi.encodePacked(lotId_, bidData.bidder, amountIn)))
    );
    ...
}
```
As shown in the code snippet, one of the parameters passed to the ECIES.decrypt() function will be the encryptedBid.bidPubKey (the invalid point provided by the malicious bidder). As we can see, the first step performed by ECIES.decrypt() will be to call the recoverSharedSecret() function, passing the invalid public key (ciphertextPubKey_) and the auction’s global privateKey_ as parameter:
```solidity
// ECIES.sol
function decrypt(
    uint256 ciphertext_,
    Point memory ciphertextPubKey_,
    uint256 privateKey_,
    uint256 salt_
) public view returns (uint256 message_) {
    // Calculate the shared secret
    // Validates the ciphertext public key is on the curve and the private key is valid
    uint256 sharedSecret = recoverSharedSecret(ciphertextPubKey_, privateKey_);
    ...
}

function recoverSharedSecret(
    Point memory ciphertextPubKey_,
    uint256 privateKey_
) public view returns (uint256) {
    ...
    Point memory p = _ecMul(ciphertextPubKey_, privateKey_);
    return p.x;
}

function _ecMul(Point memory p, uint256 scalar) private view returns (Point memory p2) {
    (bool success, bytes memory output) = address(0x07).staticcall{gas: 6000}(abi.encode(p.x, p.y, scalar));
    if (!success || output.length == 0) revert("ecMul failed.");
    p2 = abi.decode(output, (Point));
}
```
Among other things, recoverSharedSecret() will execute a scalar multiplication between the invalid public key and the global private key via the ecMul precompile. This is where the denial of servide will take place.
The ecMul precompile contract was incorporated in EIP-196. Checking the EIP’s exact semantics section, we can see that inputs will be considered invalid if “... any of the field elements (point coordinates) is equal or larger than the field modulus p, the contract fails”. Because the point submitted by the bidder had one of the x or y coordinates bigger than the field modulus p (because Axis never validated that such value was smaller than the field), the call to the ecmul precompile will fail, reverting with the “ecMul failed.” error.
Because the decryption process expects ALL the bids submitted for an auction to be decrypted prior to actually setting the auctions state to Decrypted, if only one bid decryption fails, the decryption process won’t be completed, and the whole auction process (decrypting, settling, ...) won’t be executable because the auction never reaches the Decrypted state.
High. A malicious bidder can effectively DoS the decryption process, which will prevent all actions in the protocol from being executed. This attack will make all the bids and prefunded auction funds remain stuck forever in the contract, because all the functions related to the post-concluded auction steps expect the bids to be first decrypted.

## Proof of Concept

The following proof of concept shows a reproduction of the attack mentioned above. In order to reproduce it, following these steps:
1. Inside EMPAModuleTest.sol, change the _createBidData() function so that it uses the (218882428718392752222464057452572750886963111572978236626890378946452262) point instead of the _bidPublicKey variable. This is a valid point as per Axis’ checks, but it is actually invalid given that the x coordinate is greater than the field modulus:
```solidity
// EMPAModuleTest.t.sol
function _createBidData(
    address bidder_,
    uint96 amountIn_,
    uint96 amountOut_
) internal view returns (bytes memory) {
    uint256 encryptedAmountOut = _encryptBid(_lotId, bidder_, amountIn_, amountOut_);
    return abi.encode(encryptedAmountOut, Point({x: 21888242871839275222246405745257275088696311157297823662689037894645226208584, y: 2}));
}
```
2. Paste the following code in moonraker/test/modules/auctions/EMPA/decryptAndSortBids.t.sol:
```solidity
// decryptAndSortBids.t.sol
function testBugdosDecryption()
    external
    givenLotIsCreated
    givenLotHasStarted
    givenBidIsCreated(_BID_AMOUNT, _BID_AMOUNT_OUT)
    givenBidIsCreated(_BID_AMOUNT, _BID_AMOUNT_OUT)
    givenLotHasConcluded
    givenPrivateKeyIsSubmitted
{
    vm.expectRevert("ecMul failed.");
    _module.decryptAndSortBids(_lotId, 1);
}
```
3. Run the test inside moonraker with the following command: forge test --mt testBugdosDecryption

## Recommendation

Ensure that the x and y coordinates are smaller than the field modulus inside the ECIES.sol isValid() function, adding the p.x < FIELD_MODULUS && p.y < FIELD_MODULUS check so that invalid points can’t be submitted:
```solidity
// ECIES.sol
function isValid(Point memory p) public pure returns (bool) {
    return isOnBn128(p) && !(p.x == 1 && p.y == 2) && !(p.x == 0 && p.y == 0) && (p.x < FIELD_MODULUS && p.y < FIELD_MODULUS);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a denial‑of‑service (DoS) condition that arises in the sealed‑auction module when a bidder submits an elliptic‑curve public key that is not a valid point on the AltBn128 curve. The root cause is that the ECIES library’s isValid() routine checks that the point lies on the curve, is not the generator point (1,2) and is not the point at infinity (0,0), but it omits the essential verification that both x and y coordinates are smaller than the field modulus p. Because the field modulus is a large prime (21888242871839275222246405745257275088696311157297823662689037894645226208583), a malicious bidder can craft a point whose x or y coordinate exceeds p while still satisfying the three existing checks. When such an invalid point is stored with the encrypted bid, the decryption phase later calls ECIES.decrypt(), which internally invokes recoverSharedSecret() and performs a scalar multiplication via the ecMul precompile. The precompile follows EIP‑196 semantics and rejects any point with coordinates equal to or larger than p, causing the call to revert with “ecMul failed.” Since the auction’s decryptAndSortBids() function requires every bid to be successfully decrypted before the auction state can transition to Decrypted, a single malformed point prevents the entire decryption step, leaving the auction stuck in a pre‑decryption state. Consequently, all bids remain locked and the prefunded auction funds cannot be settled, effectively freezing user assets. The issue was discovered during a security audit that examined the validation logic of the ECIES implementation and identified the missing modulus bound check. It is hard to notice because the existing checks appear to enforce curve validity, and the failure only manifests during decryption, a path that may not be exercised in routine testing. To remediate, the isValid() function should be extended to ensure p.x < FIELD_MODULUS and p.y < FIELD_MODULUS, thereby rejecting points that lie outside the finite field and preventing the ecMul precompile from reverting. This class of bug belongs to the broader category of elliptic‑curve input validation errors that can lead to protocol‑wide DoS and fund‑locking scenarios, violating the business assumption that all submitted bids can be decrypted and settled as expected. From a user’s perspective, a participant may see that their auction never reaches settlement, balances remain unchanged, and funds appear to be stuck with no way to withdraw, contrary to the expectation that a completed auction will release or return assets.
